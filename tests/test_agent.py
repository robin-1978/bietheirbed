from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pc_assistant.agent import Agent, AgentEvent
from pc_assistant.config import AppConfig
from pc_assistant.llm_provider import LLMResponse
from pc_assistant.tools.base import ToolBase
from pc_assistant.tools.registry import ToolRegistry
from typing import Any


class TestAgentEvent:
    def test_defaults(self):
        e = AgentEvent(type="thought")
        assert e.type == "thought"
        assert e.content == ""
        assert e.tool_name == ""
        assert e.tool_args == {}
        assert e.tool_result is None
        assert e.blocked is False
        assert e.iteration == 0

    def test_with_values(self):
        e = AgentEvent(
            type="tool_call",
            content="calling tool",
            tool_name="filesystem",
            tool_args={"action": "read"},
            tool_result={"content": "file data"},
            blocked=False,
            iteration=3,
        )
        assert e.type == "tool_call"
        assert e.tool_name == "filesystem"
        assert e.iteration == 3


class TestAgentInit:
    def test_default_init(self):
        agent = Agent(config=AppConfig())
        assert agent.conversation is not None
        assert agent.registry is not None

    def test_builtin_tools_registered(self):
        agent = Agent(config=AppConfig())
        tools = agent.registry.list_tools()
        assert "filesystem" in tools
        assert "shell" in tools
        assert "application" in tools
        assert "web" in tools
        assert "system" in tools
        assert "clipboard" in tools

    def test_custom_tool_registration(self):
        class CustomTool(ToolBase):
            name = "custom"
            description = "A custom tool"

            async def execute(self, **kwargs: Any) -> Any:
                return {"result": "custom"}

            def schema(self) -> dict[str, Any]:
                return {"name": self.name, "description": self.description, "parameters": {"type": "object", "properties": {}}}

        agent = Agent(config=AppConfig())
        agent.register_tool(CustomTool())
        assert "custom" in agent.registry.list_tools()


async def _collect_events(agent: Agent, user_input: str) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    async for event in agent.run(user_input):
        events.append(event)
    return events


class TestAgentRun:
    @pytest.mark.asyncio
    async def test_direct_answer(self):
        agent = Agent(config=AppConfig())
        agent._llm.chat = AsyncMock(return_value=LLMResponse(content="Hello!", finish_reason="stop"))
        events = await _collect_events(agent, "hi")
        assert any(e.type == "final_answer" and e.content == "Hello!" for e in events)

    @pytest.mark.asyncio
    async def test_thought_then_answer(self):
        agent = Agent(config=AppConfig())
        agent._llm.chat = AsyncMock(return_value=LLMResponse(content="Let me think... Hello!", finish_reason="stop"))
        events = await _collect_events(agent, "hi")
        thought_events = [e for e in events if e.type == "thought"]
        final_events = [e for e in events if e.type == "final_answer"]
        assert len(thought_events) >= 1
        assert len(final_events) >= 1

    @pytest.mark.asyncio
    async def test_tool_call_flow(self, tmp_path):
        agent = Agent(config=AppConfig())
        test_file = str(tmp_path / "test.txt")
        first = LLMResponse(
            content="Let me write a file.",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "filesystem", "arguments": {"action": "write", "path": test_file, "content": "hello"}},
            }],
        )
        second = LLMResponse(content="File written!", finish_reason="stop")
        agent._llm.chat = AsyncMock(side_effect=[first, second])
        events = await _collect_events(agent, "write a file")
        tool_calls = [e for e in events if e.type == "tool_call" and not e.blocked]
        tool_results = [e for e in events if e.type == "tool_result"]
        final = [e for e in events if e.type == "final_answer"]
        assert len(tool_calls) >= 1
        assert len(tool_results) >= 1
        assert len(final) >= 1

    @pytest.mark.asyncio
    async def test_safety_blocked(self):
        agent = Agent(config=AppConfig())
        response = LLMResponse(
            content="Deleting.",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "shell", "arguments": {"command": "rm -rf /"}},
            }],
        )
        agent._llm.chat = AsyncMock(return_value=response)
        events = await _collect_events(agent, "delete everything")
        blocked = [e for e in events if e.type == "tool_call" and e.blocked]
        assert len(blocked) >= 1

    @pytest.mark.asyncio
    async def test_confirm_callback_allows(self):
        agent = Agent(config=AppConfig(), confirm_callback=lambda n, a: True)
        response = LLMResponse(
            content="Deleting.",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "shell", "arguments": {"command": "rm -rf /"}},
            }],
        )
        second = LLMResponse(content="Done!", finish_reason="stop")
        agent._llm.chat = AsyncMock(side_effect=[response, second])
        events = await _collect_events(agent, "delete temp")
        allowed_calls = [e for e in events if e.type == "tool_call" and not e.blocked]
        assert len(allowed_calls) >= 1

    @pytest.mark.asyncio
    async def test_confirm_callback_denies(self):
        agent = Agent(config=AppConfig(), confirm_callback=lambda n, a: False)
        response = LLMResponse(
            content="Deleting.",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "shell", "arguments": {"command": "rm -rf /"}},
            }],
        )
        second = LLMResponse(content="Blocked.", finish_reason="stop")
        agent._llm.chat = AsyncMock(side_effect=[response, second])
        events = await _collect_events(agent, "delete temp")
        blocked = [e for e in events if e.type == "tool_call" and e.blocked]
        assert len(blocked) >= 1

    @pytest.mark.asyncio
    async def test_confirm_callback_exception(self):
        def bad_callback(name, args):
            raise RuntimeError("callback error")

        agent = Agent(config=AppConfig(), confirm_callback=bad_callback)
        response = LLMResponse(
            content="Deleting.",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "shell", "arguments": {"command": "rm -rf /"}},
            }],
        )
        second = LLMResponse(content="Blocked.", finish_reason="stop")
        agent._llm.chat = AsyncMock(side_effect=[response, second])
        events = await _collect_events(agent, "delete temp")
        blocked = [e for e in events if e.type == "tool_call" and e.blocked]
        assert len(blocked) >= 1

    @pytest.mark.asyncio
    async def test_tool_exception(self):
        agent = Agent(config=AppConfig())
        agent._registry.execute = AsyncMock(side_effect=RuntimeError("tool failed"))
        response = LLMResponse(
            content="Using tool.",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "filesystem", "arguments": {"action": "read", "path": "test.txt"}},
            }],
        )
        second = LLMResponse(content="Tool failed, let me try something else.", finish_reason="stop")
        agent._llm.chat = AsyncMock(side_effect=[response, second])
        events = await _collect_events(agent, "read file")
        error_results = [e for e in events if e.type == "tool_result" and e.tool_result and isinstance(e.tool_result, dict) and "error" in e.tool_result]
        assert len(error_results) >= 1

    @pytest.mark.asyncio
    async def test_iteration_limit(self):
        agent = Agent(config=AppConfig(max_iterations=2))
        tool_response = LLMResponse(
            content="Thinking...",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "filesystem", "arguments": {"action": "exists", "path": "."}},
            }],
        )
        agent._llm.chat = AsyncMock(return_value=tool_response)
        events = await _collect_events(agent, "keep going")
        limit_events = [e for e in events if e.type == "iteration_limit"]
        assert len(limit_events) >= 1

    @pytest.mark.asyncio
    async def test_string_arguments(self):
        agent = Agent(config=AppConfig())
        response = LLMResponse(
            content="Using tool.",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "filesystem", "arguments": '{"action": "exists", "path": "."}'},
            }],
        )
        second = LLMResponse(content="Done!", finish_reason="stop")
        agent._llm.chat = AsyncMock(side_effect=[response, second])
        events = await _collect_events(agent, "check file")
        tool_calls = [e for e in events if e.type == "tool_call" and not e.blocked]
        assert len(tool_calls) >= 1

    @pytest.mark.asyncio
    async def test_rate_limit(self):
        agent = Agent(config=AppConfig())
        from pc_assistant.harness.limiter import RateLimiter
        agent._limiter = RateLimiter(max_calls=1, window_seconds=60)
        agent._llm.chat = AsyncMock(return_value=LLMResponse(content="ok"))
        await _collect_events(agent, "first")
        events = await _collect_events(agent, "second")
        assert any(e.type == "error" and "Rate limit" in e.content for e in events)

    @pytest.mark.asyncio
    async def test_error_response(self):
        agent = Agent(config=AppConfig())
        agent._llm.chat = AsyncMock(return_value=LLMResponse(content="Connection failed", finish_reason="error"))
        events = await _collect_events(agent, "hello")
        assert any(e.type == "error" for e in events)


class TestAgentRunSimple:
    @pytest.mark.asyncio
    async def test_final_answer(self):
        agent = Agent(config=AppConfig())
        agent._llm.chat = AsyncMock(return_value=LLMResponse(content="Hello!", finish_reason="stop"))
        result = await agent.run_simple("hi")
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_error(self):
        agent = Agent(config=AppConfig())
        agent._llm.chat = AsyncMock(return_value=LLMResponse(content="Error occurred", finish_reason="error"))
        result = await agent.run_simple("hi")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_iteration_limit(self):
        agent = Agent(config=AppConfig(max_iterations=1))
        agent._llm.chat = AsyncMock(return_value=LLMResponse(
            content="Thinking...",
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "filesystem", "arguments": {"action": "exists", "path": "."}}}],
        ))
        result = await agent.run_simple("keep going")
        assert "Maximum iterations" in result


class TestAgentHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self):
        agent = Agent(config=AppConfig())
        agent._llm.health_check = AsyncMock(return_value=True)
        result = await agent.health_check()
        assert result is True


class TestAgentReset:
    def test_reset_conversation(self):
        agent = Agent(config=AppConfig())
        agent._conversation.add_user("hello")
        agent.reset_conversation()
        msgs = agent.conversation.get_messages()
        assert len(msgs) == 1
        assert msgs[0]["role"] == "system"
