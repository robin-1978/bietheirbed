from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Callable

from pydantic import BaseModel

from pc_assistant.config import AppConfig, load_config
from pc_assistant.context.conversation import ConversationManager
from pc_assistant.context.system_prompt import build_system_prompt
from pc_assistant.context.truncator import truncate_messages
from pc_assistant.harness.audit import AuditLogger
from pc_assistant.harness.limiter import RateLimiter
from pc_assistant.harness.recovery import RecoveryManager
from pc_assistant.harness.safety import SafetyChecker
from pc_assistant.llm_provider import LLMProvider
from pc_assistant.logger import get_logger
from pc_assistant.tools.application import ApplicationTool
from pc_assistant.tools.clipboard import ClipboardTool
from pc_assistant.tools.filesystem import FilesystemTool
from pc_assistant.tools.registry import ToolRegistry
from pc_assistant.tools.shell import ShellTool
from pc_assistant.tools.system import SystemTool
from pc_assistant.tools.web import WebTool


class AgentEvent(BaseModel):
    type: str
    content: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = {}
    tool_result: Any = None
    blocked: bool = False
    iteration: int = 0


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
        )
        self._conversation = ConversationManager()
        self._registry = ToolRegistry()
        self._safety = SafetyChecker(
            dangerous_commands=self._config.dangerous_commands,
            protected_paths=self._config.protected_paths,
        )
        self._limiter = RateLimiter()
        self._recovery = RecoveryManager()
        self._audit = AuditLogger()
        self._confirm_callback = confirm_callback
        self._system_prompt = build_system_prompt()
        self._conversation.add("system", self._system_prompt)
        self._register_builtin_tools()

    @property
    def conversation(self) -> ConversationManager:
        return self._conversation

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    async def health_check(self) -> bool:
        return await self._llm.health_check()

    def _register_builtin_tools(self) -> None:
        builtin_tools = [
            FilesystemTool(),
            ShellTool(),
            ApplicationTool(),
            WebTool(),
            SystemTool(),
            ClipboardTool(),
        ]
        for tool in builtin_tools:
            self._registry.register(tool)

    def register_tool(self, tool: Any) -> None:
        self._registry.register(tool)

    async def run(self, user_input: str) -> AsyncGenerator[AgentEvent, None]:
        if not self._limiter.is_allowed("agent"):
            yield AgentEvent(
                type="error",
                content="Rate limit exceeded. Please wait before sending another message.",
            )
            return

        self._conversation.add_user(user_input)

        for iteration in range(self._config.max_iterations):
            messages = truncate_messages(
                self._conversation.get_messages(),
                budget=self._config.context_window_budget,
            )
            tools = self._registry.all_schemas() if len(self._registry) > 0 else None

            response = await self._recovery.execute_with_recovery(
                self._llm.chat, messages, tools=tools
            )

            if response.finish_reason == "error":
                yield AgentEvent(
                    type="error",
                    content=response.content,
                    iteration=iteration,
                )
                return

            self._conversation.add_assistant(
                response.content,
                tool_calls=response.tool_calls if response.tool_calls else None,
            )

            if response.content:
                yield AgentEvent(
                    type="thought",
                    content=response.content,
                    iteration=iteration,
                )

            if not response.tool_calls:
                yield AgentEvent(
                    type="final_answer",
                    content=response.content,
                    iteration=iteration,
                )
                return

            for tool_call in response.tool_calls:
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

                try:
                    result = await self._registry.execute(tool_name, **arguments)
                    result_str = str(result)
                    self._conversation.add_tool_result(tool_call_id, result_str)
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
                    yield AgentEvent(
                        type="tool_result",
                        tool_name=tool_name,
                        tool_args=arguments,
                        tool_result={"error": str(e)},
                        content=error_msg,
                        iteration=iteration,
                    )

        yield AgentEvent(
            type="iteration_limit",
            content="Maximum iterations reached without a final answer.",
            iteration=self._config.max_iterations,
        )

    async def run_simple(self, user_input: str) -> str:
        final_answer = ""
        async for event in self.run(user_input):
            if event.type == "final_answer":
                final_answer = event.content
            elif event.type == "error":
                final_answer = event.content
            elif event.type == "iteration_limit":
                final_answer = event.content
        return final_answer

    def reset_conversation(self) -> None:
        self._conversation.clear()
        self._conversation.add("system", self._system_prompt)
