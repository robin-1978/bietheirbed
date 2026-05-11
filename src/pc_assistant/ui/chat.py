from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Awaitable

from pc_assistant.config import AppConfig
from pc_assistant.agent import Agent, AgentEvent

try:
    from rich.console import Console
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
  ____  _        _   _                ____           _
 |  _ \(_)      | | | |              |  _ \         | |
 | |_) |_  ___  | |_| |__   ___ _ __| |_) | ___  __| |
 |  _ <| |/ _ \ | __| '_ \ / _ \ '__|  _ < / _ \/ _` |
 | |_) | |  __/ | |_| | | |  __/ |  | |_) |  __/ (_| |
 |____/|_|\___|  \__|_| |_|\___|_|  |____/ \___|\__,_|
"""

_COMMANDS_HELP = """\
/exit, /quit    Save conversation and exit
/clear          Clear conversation history
/history        Show conversation history summary
/tools          List available tools
/help           Show this help message
/config         Show current configuration\
"""


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

    def _print_thought(self, content: str) -> None:
        if self._console is not None:
            self._console.print(Text(content, style="thought"))
        else:
            print(f"  [thought] {content}")

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

    def _print_final_answer(self, content: str) -> None:
        if self._console is not None:
            self._console.print()
            self._console.print(Markdown(content))
            self._console.print()
        else:
            print(f"\n{content}\n")

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

    def _confirm_action(self, title: str, details: str) -> bool:
        if self._console is not None:
            self._console.print(
                Panel(
                    details,
                    title=f"[warning]⚠ {title}[/warning]",
                    border_style="yellow",
                    expand=False,
                )
            )
        else:
            print(f"\n⚠ {title}")
            print(details)

        try:
            answer = input("Proceed? (y/n): ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

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
                table.add_row("LLM Server", self._config.llm_server_url)
                table.add_row("Model", self._config.llm_model_name or "(not set)")
                table.add_row("Max Iterations", str(self._config.max_iterations))
                table.add_row("Shell Timeout", str(self._config.shell_timeout))
                table.add_row("Context Budget", str(self._config.context_window_budget))
                table.add_row("Log File", self._config.log_file)
                table.add_row("Working Dir", self._config.working_directory)
                self._console.print(table)
            else:
                print(f"  LLM Server: {self._config.llm_server_url}")
                print(f"  Model:      {self._config.llm_model_name or '(not set)'}")
                print(f"  Max Iters:  {self._config.max_iterations}")
                print(f"  Shell Timeout: {self._config.shell_timeout}")
                print(f"  Context Budget: {self._config.context_window_budget}")
                print(f"  Log File:   {self._config.log_file}")
                print(f"  Working Dir: {self._config.working_directory}")
            return True

        self._print_warning(f"Unknown command: {command}")
        return True

    async def _process_events(self, user_input: str) -> None:
        if self._agent is None:
            self._print_error("Agent not initialized.")
            return

        async for event in self._agent.run(user_input):
            if event.type == "thought":
                self._print_thought(event.content)

            elif event.type == "tool_call":
                self._print_tool_call(event.tool_name, event.tool_args)

            elif event.type == "tool_result":
                result_str = str(event.tool_result) if event.tool_result is not None else event.content
                is_error = isinstance(event.tool_result, dict) and "error" in event.tool_result
                self._print_tool_result(event.tool_name, result_str, is_error)

            elif event.type == "final_answer":
                self._print_final_answer(event.content)

            elif event.type == "error":
                self._print_error(event.content)

            elif event.type == "iteration_limit":
                self._print_warning(event.content)

    async def run(self) -> None:
        self._running = True
        self._show_welcome()

        while self._running:
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
