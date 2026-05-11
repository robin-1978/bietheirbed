from __future__ import annotations

import asyncio
import json
import re
import signal
import sys
import threading
import time
from typing import Any, Callable

from pc_assistant.config import AppConfig
from pc_assistant.agent import Agent, AgentEvent

try:
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text
    from rich.theme import Theme
    from rich.table import Table

    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

try:
    from rich.prompt import Prompt

    _HAS_RICH_PROMPT = True
except ImportError:
    _HAS_RICH_PROMPT = False


_WELCOME_ART = r"""
  ____  _        _   _               ____           _
 |  _ \(_)      | | | |             |  _ \         | |
 | |_) |_  ___  | |_| |__   ___ _ __| |_) | ___  __| |
 |  _ <| |/ _ \ | __| '_ \ / _ \ '__|  _ < / _ \/ _` |
 | |_) | |  __/ | |_| | | |  __/ |  | |_) |  __/ (_| |
 |____/|_|\___|  \__|_| |_|\___|_|  |____/ \___|\__,_|
"""

_COMMANDS_HELP = """\
/exit, /quit    Save conversation and exit
/clear          Clear conversation history
/memory         Show remembered user preferences
/memory clear   Clear all memories
/history        Show conversation history summary
/tools          List available tools
/status         Show detailed agent status
/help           Show this help message
/config         Show current configuration\
"""

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class _Spinner:
    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._message = ""
        self._frame_idx = 0

    def start(self, message: str = "") -> None:
        self.stop()
        self._message = message
        self._running = True
        self._frame_idx = 0
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def update(self, message: str) -> None:
        self._message = message

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()

    def _spin(self) -> None:
        while self._running:
            frame = _SPINNER_FRAMES[self._frame_idx % len(_SPINNER_FRAMES)]
            msg = f"\r  {frame} {self._message}" if self._message else f"\r  {frame}"
            sys.stdout.write(msg)
            sys.stdout.flush()
            self._frame_idx += 1
            time.sleep(0.08)


class ChatUI:
    def __init__(
        self,
        config: AppConfig,
        confirm_callback: Callable[[str, str], bool] | None = None,
    ) -> None:
        self._config = config
        self._agent: Agent | None = None
        self._confirm_callback = confirm_callback
        self._running = False
        self._cancelled = False
        self._spinner = _Spinner()
        if _HAS_RICH:
            custom_theme = Theme({
                "thought": "dim italic",
                "tool_name": "cyan bold",
                "tool_args": "cyan",
                "tool_result": "dim",
                "final_answer": "bold",
                "error": "red bold",
                "warning": "yellow",
                "prompt": "green bold",
                "ai_label": "blue bold",
                "think_label": "dim italic",
                "status_bar": "dim",
            })
            self._console = Console(theme=custom_theme)
        else:
            self._console = None

    def _print(self, *args: Any, **kwargs: Any) -> None:
        if self._console is not None:
            self._console.print(*args, **kwargs)
        else:
            plain = " ".join(str(a) for a in args)
            print(plain)

    def _print_tool_call(self, name: str, arguments: dict[str, Any]) -> None:
        if self._console is not None:
            args_str = json.dumps(arguments, indent=2, ensure_ascii=False)
            self._console.print(
                Panel(
                    f"[tool_args]{args_str}[/tool_args]",
                    title=f"[tool_name]🔧 {name}[/tool_name]",
                    border_style="cyan",
                    expand=False,
                )
            )
        else:
            print(f"  [tool: {name}] {json.dumps(arguments, ensure_ascii=False)}")

    def _print_tool_result(self, name: str, result: str, is_error: bool = False) -> None:
        if self._console is not None:
            style = "error" if is_error else "tool_result"
            truncated = result[:500] + "..." if len(result) > 500 else result
            self._console.print(
                Text(f"  ← {name}: {truncated}", style=style)
            )
        else:
            print(f"  ← {name}: {result[:200]}")

    def _print_error(self, message: str) -> None:
        if self._console is not None:
            self._console.print(f"[error]✗ {message}[/error]")
        else:
            print(f"ERROR: {message}")

    def _print_warning(self, message: str) -> None:
        if self._console is not None:
            self._console.print(f"[warning]⚠ {message}[/warning]")
        else:
            print(f"WARNING: {message}")

    def _render_status_bar(self) -> None:
        if self._agent is None or self._console is None:
            return
        status = self._agent.get_status()
        provider = status.get("provider", "unknown")
        model = status.get("model", "default")
        connected = "🟢" if status.get("connected") else "🔴"
        agent_status = status.get("status", "ready")
        turns = status.get("conversation_turns", 0)
        total_tokens = status.get("total_tokens", 0)
        status_text = f" {connected} {provider} | {model} | {agent_status} | turns: {turns} | tokens: {total_tokens} "
        self._console.print(
            Panel(status_text, style="status_bar", border_style="dim", expand=False)
        )

    def _show_welcome(self) -> None:
        if self._console is not None:
            self._console.print(_WELCOME_ART, style="bold green", highlight=False)
            from pc_assistant import __version__
            self._console.print(f"  [bold]v{__version__}[/bold]  •  Type [bold]/help[/bold] for commands\n")
        else:
            from pc_assistant import __version__
            print(f"PC Assistant v{__version__}")
            print("Type /help for commands\n")

    def _get_input(self) -> str | None:
        if _HAS_RICH_PROMPT and self._console is not None:
            try:
                return Prompt.ask("[prompt]You>[/prompt]", console=self._console)
            except (EOFError, KeyboardInterrupt):
                return None
        else:
            try:
                return input("You> ").strip()
            except (EOFError, KeyboardInterrupt):
                return None

    def _handle_user_command(self, command: str) -> bool:
        cmd = command.lower().strip()

        if cmd in ("/exit", "/quit"):
            self._print("[dim]Goodbye![/dim]" if self._console else "Goodbye!")
            self._running = False
            return True

        if cmd == "/clear":
            if self._agent is not None:
                self._agent.reset_conversation()
            self._print("[dim]Conversation history cleared.[/dim]" if self._console else "Conversation history cleared.")
            return True

        if cmd == "/history":
            if self._agent is None:
                self._print_warning("No agent initialized yet.")
                return True
            messages = self._agent.conversation.get_messages()
            if not messages:
                self._print("[dim]No conversation history.[/dim]" if self._console else "No conversation history.")
                return True
            if self._console is not None:
                table = Table(title="Conversation History", show_lines=True)
                table.add_column("#", style="dim", width=4)
                table.add_column("Role", style="bold", width=10)
                table.add_column("Content", width=60)
                for i, msg in enumerate(messages):
                    role = msg.get("role", "?")
                    content = msg.get("content", "")
                    if len(content) > 120:
                        content = content[:117] + "..."
                    table.add_row(str(i + 1), role, content)
                self._console.print(table)
            else:
                for i, msg in enumerate(messages):
                    role = msg.get("role", "?")
                    content = msg.get("content", "")[:80]
                    print(f"  {i + 1}. [{role}] {content}")
            return True

        if cmd == "/tools":
            if self._agent is None:
                self._print_warning("No agent initialized yet.")
                return True
            tools = self._agent.registry.list_tools()
            if not tools:
                self._print("[dim]No tools registered.[/dim]" if self._console else "No tools registered.")
                return True
            if self._console is not None:
                table = Table(title="Available Tools")
                table.add_column("Tool", style="cyan bold")
                for t in tools:
                    table.add_row(t)
                self._console.print(table)
            else:
                print("Available tools:")
                for t in tools:
                    print(f"  - {t}")
            return True

        if cmd == "/help":
            if self._console is not None:
                self._console.print(
                    Panel(
                        _COMMANDS_HELP,
                        title="Commands",
                        border_style="green",
                        expand=False,
                    )
                )
            else:
                print("Commands:")
                print(_COMMANDS_HELP)
            return True

        if cmd == "/config":
            if self._console is not None:
                table = Table(title="Configuration", show_lines=True)
                table.add_column("Key", style="bold")
                table.add_column("Value")
                table.add_row("Provider", self._config.llm_provider)
                table.add_row("LLM Server", self._config.llm_server_url)
                table.add_row("Model", self._config.llm_model_name or "(not set)")
                table.add_row("Max Iterations", str(self._config.max_iterations))
                table.add_row("Shell Timeout", str(self._config.shell_timeout))
                table.add_row("Context Budget", str(self._config.context_window_budget))
                table.add_row("Log File", self._config.log_file)
                table.add_row("Working Dir", self._config.working_directory)
                self._console.print(table)
            else:
                print(f"  Provider:    {self._config.llm_provider}")
                print(f"  LLM Server:  {self._config.llm_server_url}")
                print(f"  Model:       {self._config.llm_model_name or '(not set)'}")
                print(f"  Max Iters:   {self._config.max_iterations}")
                print(f"  Working Dir: {self._config.working_directory}")
            return True

        if cmd == "/status":
            if self._agent is None:
                self._print_warning("No agent initialized yet.")
                return True
            status = self._agent.get_status()
            if self._console is not None:
                table = Table(title="Agent Status", show_lines=True)
                table.add_column("Property", style="bold")
                table.add_column("Value")
                table.add_row("Provider", status["provider"])
                table.add_row("Model", status["model"])
                table.add_row("Connected", "🟢 Yes" if status["connected"] else "🔴 No")
                table.add_row("Status", status["status"])
                table.add_row("Platform", status["platform"])
                table.add_row("Working Dir", status["working_directory"])
                table.add_row("Conversation Turns", str(status["conversation_turns"]))
                table.add_row("Total Iterations", str(status["total_iterations"]))
                table.add_row("Prompt Tokens", str(status["total_prompt_tokens"]))
                table.add_row("Completion Tokens", str(status["total_completion_tokens"]))
                table.add_row("Total Tokens", str(status["total_tokens"]))
                table.add_row("Memory Items", str(status["memory_items"]))
                table.add_row("Tools", ", ".join(status["tools"]))
                self._console.print(table)
            else:
                for k, v in status.items():
                    print(f"  {k}: {v}")
            return True

        if cmd == "/memory clear":
            if self._agent is None:
                self._print_warning("No agent initialized yet.")
                return True
            self._agent.memory.clear()
            self._print("[dim]All memories cleared.[/dim]" if self._console else "All memories cleared.")
            return True

        if cmd == "/memory":
            if self._agent is None:
                self._print_warning("No agent initialized yet.")
                return True
            items = self._agent.memory.get_all()
            if not items:
                self._print("[dim]No memories stored yet. I'll learn your preferences as we chat![/dim]" if self._console else "No memories stored yet.")
                return True
            if self._console is not None:
                table = Table(title="🧠 User Memory", show_lines=True)
                table.add_column("Category", style="bold", width=12)
                table.add_column("Key", width=25)
                table.add_column("Value", width=40)
                table.add_column("Access", width=6)
                for item in sorted(items, key=lambda x: x.category):
                    table.add_row(item.category, item.key, item.value[:60], str(item.access_count))
                self._console.print(table)
            else:
                for item in items:
                    print(f"  [{item.category}] {item.key}: {item.value}")
            return True

        self._print_warning(f"Unknown command: {command}")
        return True

    async def _process_events(self, user_input: str) -> None:
        if self._agent is None:
            self._print_error("Agent not initialized.")
            return

        self._cancelled = False
        self._agent._cancelled = False

        think_start_time: float | None = None
        think_text_parts: list[str] = []
        in_think_display = False
        first_content_received = False
        spinner_active = False

        def _cancel_handler() -> None:
            self._cancelled = True
            if self._agent is not None:
                self._agent.cancel()

        loop = asyncio.get_event_loop()
        try:
            loop.add_signal_handler(signal.SIGINT, _cancel_handler)
        except (NotImplementedError, OSError):
            pass

        try:
            async for event in self._agent.run(user_input):
                if self._cancelled:
                    self._spinner.stop()
                    spinner_active = False
                    self._print_warning("Operation cancelled.")
                    break

                if event.type == "stream_start":
                    self._spinner.start("Thinking...")
                    spinner_active = True
                    first_content_received = False

                elif event.type == "think_start":
                    think_start_time = time.time()
                    think_text_parts = []
                    in_think_display = True
                    self._spinner.stop()
                    spinner_active = False
                    if self._console is not None:
                        self._console.print()
                        self._console.print("[think_label]💭 Thinking...[/think_label]")
                    else:
                        print("\n  💭 Thinking...")

                elif event.type == "stream_think_delta":
                    if not first_content_received:
                        first_content_received = True
                    think_text_parts.append(event.content)
                    sys.stdout.write(event.content)
                    sys.stdout.flush()

                elif event.type == "think_end":
                    in_think_display = False
                    elapsed = time.time() - think_start_time if think_start_time else 0
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    full_think = "".join(think_text_parts)
                    summary = full_think[:80].replace("\n", " ")
                    if len(full_think) > 80:
                        summary += "..."
                    if self._console is not None:
                        self._console.print(
                            f"[think_label]💭 Thought for {elapsed:.1f}s: {summary}[/think_label]"
                        )
                    else:
                        print(f"  💭 Thought for {elapsed:.1f}s: {summary}")
                    think_start_time = None

                elif event.type == "stream_delta":
                    if not first_content_received:
                        first_content_received = True
                        self._spinner.stop()
                        spinner_active = False
                        if self._console is not None:
                            self._console.print()
                            self._console.print("[ai_label]AI>[/ai_label]", end=" ")
                        else:
                            print("\nAI> ", end="", flush=True)
                    sys.stdout.write(event.content)
                    sys.stdout.flush()

                elif event.type == "stream_end":
                    if first_content_received:
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                    if spinner_active:
                        self._spinner.stop()
                        spinner_active = False

                elif event.type == "thought":
                    pass

                elif event.type == "tool_call":
                    if event.blocked:
                        self._print_warning(f"Blocked: {event.content}")
                    else:
                        self._spinner.start(f"Executing {event.tool_name}...")
                        spinner_active = True
                        self._print_tool_call(event.tool_name, event.tool_args)

                elif event.type == "tool_result":
                    self._spinner.stop()
                    spinner_active = False
                    result_str = str(event.tool_result) if event.tool_result is not None else event.content
                    is_error = isinstance(event.tool_result, dict) and "error" in event.tool_result
                    self._print_tool_result(event.tool_name, result_str, is_error)

                elif event.type == "final_answer":
                    if spinner_active:
                        self._spinner.stop()
                        spinner_active = False
                    if self._console is not None and event.content:
                        try:
                            self._console.print()
                            self._console.print(Markdown(event.content))
                            self._console.print()
                        except Exception:
                            print(f"\n{event.content}\n")
                    elif event.content:
                        print(f"\n{event.content}\n")

                elif event.type == "error":
                    if spinner_active:
                        self._spinner.stop()
                        spinner_active = False
                    self._print_error(event.content)

                elif event.type == "iteration_limit":
                    if spinner_active:
                        self._spinner.stop()
                        spinner_active = False
                    self._print_warning(event.content)

                elif event.type == "cancelled":
                    if spinner_active:
                        self._spinner.stop()
                        spinner_active = False
                    self._print_warning("Operation cancelled by user.")

        except KeyboardInterrupt:
            _cancel_handler()
            if spinner_active:
                self._spinner.stop()
            self._print_warning("Operation interrupted.")
        finally:
            try:
                loop.remove_signal_handler(signal.SIGINT)
            except (NotImplementedError, OSError):
                pass
            if spinner_active:
                self._spinner.stop()

    async def run(self) -> None:
        self._running = True
        self._show_welcome()

        while self._running:
            self._render_status_bar()
            user_input = self._get_input()

            if user_input is None:
                self._print("\n[dim]Goodbye![/dim]" if self._console else "\nGoodbye!")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.startswith("/"):
                self._handle_user_command(user_input)
                continue

            await self._process_events(user_input)
