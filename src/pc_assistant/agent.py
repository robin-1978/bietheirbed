from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, AsyncGenerator, Callable

from pydantic import BaseModel

from pc_assistant.config import AppConfig, load_config
from pc_assistant.context.conversation import ConversationManager
from pc_assistant.context.memory import UserMemory
from pc_assistant.context.system_prompt import build_system_prompt
from pc_assistant.context.truncator import truncate_messages
from pc_assistant.harness.audit import AuditLogger
from pc_assistant.harness.limiter import RateLimiter
from pc_assistant.harness.safety import SafetyChecker
from pc_assistant.llm_provider import LLMProvider, LLMResponse
from pc_assistant.logger import get_logger
from pc_assistant.platform_ import get_platform
from pc_assistant.tools.application import ApplicationTool
from pc_assistant.tools.clipboard import ClipboardTool
from pc_assistant.tools.filesystem import FilesystemTool
from pc_assistant.tools.registry import ToolRegistry
from pc_assistant.tools.shell import ShellTool
from pc_assistant.tools.system import SystemTool
from pc_assistant.tools.web import WebTool
from pc_assistant.tools.memory_tool import MemoryTool
from pc_assistant.tools.weather import WeatherTool
from pc_assistant.tools.exchange import ExchangeTool
from pc_assistant.tools.timer import TimerTool


class AgentEvent(BaseModel):
    type: str
    content: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = {}
    tool_result: Any = None
    blocked: bool = False
    iteration: int = 0


_THINK_OPEN = re.compile(r"<think[^>]*>", re.IGNORECASE)
_THINK_CLOSE = re.compile(r"</think\s*>", re.IGNORECASE)


def _strip_think_tags(text: str) -> tuple[str, str]:
    thinking = ""
    remaining = text
    while True:
        m_open = _THINK_OPEN.search(remaining)
        if m_open is None:
            break
        m_close = _THINK_CLOSE.search(remaining, m_open.end())
        if m_close is None:
            thinking += remaining[m_open.end():]
            remaining = remaining[:m_open.start()]
            break
        thinking += remaining[m_open.end():m_close.start()]
        remaining = remaining[:m_open.start()] + remaining[m_close.end():]
    return remaining.strip(), thinking.strip()


def _compute_call_signature(tool_name: str, arguments: dict[str, Any]) -> str:
    args_json = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    args_hash = hashlib.md5(args_json.encode()).hexdigest()[:8]
    return f"{tool_name}:{args_hash}"


def _build_date_context() -> str:
    now = datetime.now()
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return f"Current date: {now.strftime('%Y-%m-%d')} ({weekday_names[now.weekday()]})\nCurrent time: {now.strftime('%H:%M:%S')}"


class _ThinkStreamParser:
    def __init__(self) -> None:
        self._in_think = False
        self._buffer = ""
        self._think_content = ""
        self._clean_content = ""

    @property
    def in_think(self) -> bool:
        return self._in_think

    @property
    def think_content(self) -> str:
        return self._think_content

    @property
    def clean_content(self) -> str:
        return self._clean_content

    def feed(self, delta: str) -> list[tuple[str, str]]:
        self._buffer += delta
        events: list[tuple[str, str]] = []

        while self._buffer:
            if self._in_think:
                close_match = _THINK_CLOSE.search(self._buffer)
                if close_match:
                    text = self._buffer[:close_match.start()]
                    if text:
                        self._think_content += text
                        events.append(("stream_think_delta", text))
                    self._in_think = False
                    self._buffer = self._buffer[close_match.end():]
                    events.append(("think_end", ""))
                else:
                    if _THINK_OPEN.search(self._buffer):
                        potential_partial = self._buffer
                        self._buffer = ""
                        break
                    text = self._buffer
                    self._think_content += text
                    if text:
                        events.append(("stream_think_delta", text))
                    self._buffer = ""
            else:
                open_match = _THINK_OPEN.search(self._buffer)
                if open_match:
                    before = self._buffer[:open_match.start()]
                    if before:
                        self._clean_content += before
                        events.append(("stream_delta", before))
                    self._in_think = True
                    self._buffer = self._buffer[open_match.end():]
                    events.append(("think_start", ""))
                else:
                    if "</think" in self._buffer or "<thi" in self._buffer:
                        potential_partial = self._buffer
                        self._buffer = ""
                        break
                    text = self._buffer
                    self._clean_content += text
                    if text:
                        events.append(("stream_delta", text))
                    self._buffer = ""

        return events

    def flush(self) -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []
        if self._buffer:
            if self._in_think:
                self._think_content += self._buffer
                events.append(("stream_think_delta", self._buffer))
            else:
                self._clean_content += self._buffer
                events.append(("stream_delta", self._buffer))
            self._buffer = ""
        return events


class Agent:
    def __init__(
        self,
        config: AppConfig | None = None,
        confirm_callback: Callable[[str, dict[str, Any]], bool] | None = None,
    ) -> None:
        self._config = config or load_config()
        self._logger = get_logger("agent")
        self._llm = LLMProvider(
            server_url=self._config.llm_server_url,
            model_name=self._config.llm_model_name,
            provider=self._config.llm_provider,
            api_key=self._config.llm_api_key,
            api_base=self._config.llm_api_base,
            timeout=self._config.llm_timeout,
        )
        self._conversation = ConversationManager()
        self._memory = UserMemory()
        self._safety = SafetyChecker(
            dangerous_commands=self._config.dangerous_commands,
            protected_paths=self._config.protected_paths,
        )
        self._registry = ToolRegistry(safety=self._safety)
        self._limiter = RateLimiter()
        self._audit = AuditLogger()
        self._confirm_callback = confirm_callback
        self._cancelled = False
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_iterations = 0
        self._current_status = "ready"
        self._connected = False
        self._system_prompt = build_system_prompt(
            working_directory=self._config.working_directory,
        )
        self._conversation.set_system_context(self._system_prompt)
        self._register_builtin_tools()

    @property
    def conversation(self) -> ConversationManager:
        return self._conversation

    @property
    def memory(self) -> UserMemory:
        return self._memory

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def cancel(self) -> None:
        self._cancelled = True

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": self._config.llm_provider,
            "model": self._config.llm_model_name or "default",
            "status": self._current_status,
            "connected": self._connected,
            "platform": get_platform(),
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "total_iterations": self._total_iterations,
            "conversation_turns": len([m for m in self._conversation.get_messages() if m["role"] == "user"]),
            "memory_items": len(self._memory),
            "tools": self._registry.list_tools(),
            "working_directory": self._config.working_directory,
        }

    async def health_check(self) -> bool:
        result = await self._llm.health_check()
        self._connected = result
        return result

    def _register_builtin_tools(self) -> None:
        builtin_tools = [
            FilesystemTool(),
            ShellTool(),
            ApplicationTool(),
            WebTool(),
            SystemTool(),
            ClipboardTool(),
            MemoryTool(memory=self._memory),
            WeatherTool(),
            ExchangeTool(),
            TimerTool(),
        ]
        for tool in builtin_tools:
            self._registry.register(tool)

    def register_tool(self, tool: Any) -> None:
        self._registry.register(tool)

    @staticmethod
    def _ensure_system_first(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not messages:
            return messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        return system_msgs + other_msgs

    async def _call_llm_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_retries: int = 3,
    ) -> LLMResponse | None:
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                return await self._llm.chat(messages, tools=tools)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(0.5 * (2 ** attempt))
        if last_error is not None:
            return LLMResponse(content=f"LLM request failed after retries: {last_error}", finish_reason="error")
        return None

    async def run(self, user_input: str) -> AsyncGenerator[AgentEvent, None]:
        if not self._limiter.is_allowed("agent"):
            yield AgentEvent(
                type="error",
                content="Rate limit exceeded. Please wait before sending another message.",
            )
            return

        self._cancelled = False
        self._current_status = "thinking"
        self._conversation.add_user(user_input)

        memory_context = self._memory.build_context_string()
        if memory_context:
            full_system = self._system_prompt + "\n\n" + memory_context
        else:
            full_system = self._system_prompt
        self._conversation.set_system_context(full_system)

        recent_calls: list[str] = []
        max_recent_calls = 10
        empty_response_count = 0
        max_empty_retries = 2

        for iteration in range(self._config.max_iterations):
            if self._cancelled:
                yield AgentEvent(type="cancelled", content="Operation cancelled by user.", iteration=iteration)
                self._current_status = "ready"
                return

            self._current_status = "thinking"
            self._total_iterations += 1

            messages = self._conversation.get_messages_for_llm()
            messages = truncate_messages(
                messages,
                budget=self._config.context_window_budget,
            )
            messages = self._ensure_system_first(messages)
            tools = self._registry.all_schemas() if len(self._registry) > 0 else None

            full_content = ""
            tool_calls_from_stream: list[dict[str, Any]] = []
            finish_reason = ""
            stream_had_error = False
            think_parser = _ThinkStreamParser()
            thinking_from_field = False

            yield AgentEvent(type="stream_start", iteration=iteration)

            try:
                async for chunk in self._llm.chat_stream(messages, tools=tools, max_tokens=self._config.max_tokens):
                    if self._cancelled:
                        yield AgentEvent(type="cancelled", content="Operation cancelled by user.", iteration=iteration)
                        self._current_status = "ready"
                        return

                    if chunk.finish_reason == "error":
                        yield AgentEvent(
                            type="error",
                            content=chunk.delta_content,
                            iteration=iteration,
                        )
                        stream_had_error = True
                        break

                    if chunk.delta_thinking:
                        if not thinking_from_field:
                            thinking_from_field = True
                            yield AgentEvent(type="think_start", iteration=iteration)
                        yield AgentEvent(
                            type="stream_think_delta",
                            content=chunk.delta_thinking,
                            iteration=iteration,
                        )

                    if chunk.delta_content:
                        full_content += chunk.delta_content
                        parsed_events = think_parser.feed(chunk.delta_content)
                        for evt_type, evt_content in parsed_events:
                            yield AgentEvent(
                                type=evt_type,
                                content=evt_content,
                                iteration=iteration,
                            )

                    if chunk.delta_tool_calls:
                        tool_calls_from_stream = chunk.delta_tool_calls

                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason

                    if chunk.usage:
                        prompt_tokens = chunk.usage.get("prompt_tokens") or chunk.usage.get("input_tokens") or 0
                        completion_tokens = chunk.usage.get("completion_tokens") or chunk.usage.get("output_tokens") or 0
                        self._total_prompt_tokens += int(prompt_tokens)
                        self._total_completion_tokens += int(completion_tokens)
            except Exception as e:
                error_msg = str(e)
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    error_msg = (
                        f"LLM request timed out after {self._config.llm_timeout}s. "
                        "Possible causes: prompt too long, model is busy, or server overloaded. "
                        "You can increase PC_LLM_TIMEOUT in config if needed."
                    )
                yield AgentEvent(
                    type="error",
                    content=f"LLM stream error: {error_msg}",
                    iteration=iteration,
                )
                stream_had_error = True

            if stream_had_error:
                self._current_status = "ready"
                return

            self._connected = True

            remaining_events = think_parser.flush()
            for evt_type, evt_content in remaining_events:
                yield AgentEvent(type=evt_type, content=evt_content, iteration=iteration)

            if think_parser.in_think:
                yield AgentEvent(type="think_end", content="", iteration=iteration)

            if thinking_from_field:
                yield AgentEvent(type="think_end", content="", iteration=iteration)

            clean_content, thinking_content = _strip_think_tags(full_content)

            yield AgentEvent(type="stream_end", iteration=iteration)

            if thinking_content:
                yield AgentEvent(
                    type="thought",
                    content=thinking_content,
                    iteration=iteration,
                )

            if tool_calls_from_stream:
                self._conversation.add_assistant(
                    clean_content or full_content,
                    tool_calls=tool_calls_from_stream,
                )
                for tool_call in tool_calls_from_stream:
                    if self._cancelled:
                        yield AgentEvent(type="cancelled", content="Operation cancelled by user.", iteration=iteration)
                        self._current_status = "ready"
                        return

                    func = tool_call.get("function", {})
                    tool_name = func.get("name", "")
                    arguments = func.get("arguments", {})
                    tool_call_id = tool_call.get("id", "")

                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except (json.JSONDecodeError, TypeError):
                            arguments = {}

                    if not isinstance(arguments, dict):
                        arguments = {}

                    call_sig = _compute_call_signature(tool_name, arguments)
                    if call_sig in recent_calls:
                        self._audit.log(
                            action="loop_detected",
                            tool=tool_name,
                            parameters=arguments,
                            allowed=False,
                            reason=f"Repeated tool call detected: {tool_name}",
                        )
                        yield AgentEvent(
                            type="iteration_limit",
                            content=f"Repeated tool call detected ({tool_name}), possible infinite loop. Terminated.",
                            iteration=iteration,
                        )
                        self._current_status = "ready"
                        return

                    recent_calls.append(call_sig)
                    if len(recent_calls) > max_recent_calls:
                        recent_calls.pop(0)

                    safety_result = self._safety.check_tool_call(tool_name, arguments)

                    if not safety_result:
                        user_confirmed = False
                        if self._confirm_callback is not None:
                            try:
                                user_confirmed = self._confirm_callback(tool_name, arguments)
                            except Exception:
                                user_confirmed = False

                        if user_confirmed:
                            self._audit.log(
                                action="tool_call_confirmed",
                                tool=tool_name,
                                parameters=arguments,
                                allowed=True,
                                reason=f"User confirmed override of: {safety_result.reason}",
                            )
                        else:
                            self._audit.log(
                                action="tool_call_blocked",
                                tool=tool_name,
                                parameters=arguments,
                                allowed=False,
                                reason=safety_result.reason,
                            )
                            yield AgentEvent(
                                type="tool_call",
                                tool_name=tool_name,
                                tool_args=arguments,
                                blocked=True,
                                content=safety_result.reason,
                                iteration=iteration,
                            )
                            self._conversation.add_tool_result(
                                tool_call_id,
                                f"Blocked: {safety_result.reason}",
                            )
                            continue

                    yield AgentEvent(
                        type="tool_call",
                        tool_name=tool_name,
                        tool_args=arguments,
                        iteration=iteration,
                    )

                    self._audit.log(
                        action="tool_call",
                        tool=tool_name,
                        parameters=arguments,
                        allowed=True,
                    )

                    self._current_status = f"executing_{tool_name}"

                    try:
                        result = await self._registry.execute(tool_name, **arguments)
                        result_str = str(result)
                        max_result_chars = 3000
                        if len(result_str) > max_result_chars:
                            head_size = max_result_chars * 2 // 3
                            tail_size = max_result_chars - head_size
                            omitted = len(result_str) - max_result_chars
                            result_str = (
                                result_str[:head_size]
                                + f"\n\n... [{omitted} chars omitted] ...\n\n"
                                + result_str[-tail_size:]
                            )
                        self._conversation.add_tool_result(tool_call_id, result_str)
                        self._current_status = "thinking"
                        yield AgentEvent(
                            type="tool_result",
                            tool_name=tool_name,
                            tool_args=arguments,
                            tool_result=result,
                            content=result_str,
                            iteration=iteration,
                        )
                    except Exception as e:
                        error_msg = f"Error: {e}"
                        self._conversation.add_tool_result(tool_call_id, error_msg)
                        self._current_status = "thinking"
                        yield AgentEvent(
                            type="tool_result",
                            tool_name=tool_name,
                            tool_args=arguments,
                            tool_result={"error": str(e)},
                            content=error_msg,
                            iteration=iteration,
                        )
            else:
                if finish_reason == "length" and clean_content:
                    self._conversation.add_assistant(clean_content)
                    yield AgentEvent(
                        type="final_answer",
                        content=clean_content,
                        iteration=iteration,
                    )
                    self._current_status = "ready"
                    return

                if not clean_content and not full_content:
                    empty_response_count += 1
                    if empty_response_count > max_empty_retries:
                        self._conversation.add_assistant("I was unable to generate a response. Please try again.")
                        yield AgentEvent(
                            type="final_answer",
                            content="I was unable to generate a response. Please try again.",
                            iteration=iteration,
                        )
                        self._current_status = "ready"
                        return
                    self._conversation.add("user", "[System] You did not produce any output. Please respond to the user's question.")
                    continue

                if not clean_content and full_content:
                    empty_response_count += 1
                    if empty_response_count > max_empty_retries:
                        self._conversation.add_assistant("I was unable to generate a visible response. Please try again.")
                        yield AgentEvent(
                            type="final_answer",
                            content="I was unable to generate a visible response. Please try again.",
                            iteration=iteration,
                        )
                        self._current_status = "ready"
                        return
                    self._conversation.add("user", "Please provide your answer based on your thinking.")
                    continue

                empty_response_count = 0
                self._conversation.add_assistant(clean_content or full_content)
                yield AgentEvent(
                    type="final_answer",
                    content=clean_content or full_content,
                    iteration=iteration,
                )
                self._current_status = "ready"
                return

        yield AgentEvent(
            type="iteration_limit",
            content="Maximum iterations reached without a final answer.",
            iteration=self._config.max_iterations,
        )
        self._current_status = "ready"

    async def run_simple(self, user_input: str) -> str:
        final_answer = ""
        async for event in self.run(user_input):
            if event.type == "final_answer":
                final_answer = event.content
            elif event.type == "error":
                final_answer = event.content
            elif event.type == "iteration_limit":
                final_answer = event.content
            elif event.type == "cancelled":
                final_answer = event.content
        return final_answer

    def reset_conversation(self) -> None:
        self._conversation.clear()
        self._system_prompt = build_system_prompt(
            working_directory=self._config.working_directory,
        )
        memory_context = self._memory.build_context_string()
        if memory_context:
            full_system = self._system_prompt + "\n\n" + memory_context
        else:
            full_system = self._system_prompt
        self._conversation.set_system_context(full_system)
