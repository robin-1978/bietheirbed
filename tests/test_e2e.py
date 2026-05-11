from __future__ import annotations

from unittest.mock import AsyncMock
import pytest
from pc_assistant.config import AppConfig
from pc_assistant.agent import Agent, AgentEvent
from pc_assistant.llm_provider import LLMResponse
from pc_assistant.tools.filesystem import FilesystemTool


async def _collect_events(agent: Agent, user_input: str) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    async for event in agent.run(user_input):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_agent_rate_limit():
    config = AppConfig()
    agent = Agent(config=config)
    from pc_assistant.harness.limiter import RateLimiter
    agent._limiter = RateLimiter(max_calls=1, window_seconds=60)
    agent._llm.chat = AsyncMock(return_value=LLMResponse(content="ok"))
    await _collect_events(agent, "first message")
    events = await _collect_events(agent, "second message")
    assert any(e.type == "error" and "Rate limit" in e.content for e in events)


@pytest.mark.asyncio
async def test_agent_returns_llm_response():
    config = AppConfig()
    agent = Agent(config=config)
    agent._llm.chat = AsyncMock(return_value=LLMResponse(content="Hello!"))
    events = await _collect_events(agent, "hi")
    assert any(e.type == "final_answer" and e.content == "Hello!" for e in events)


@pytest.mark.asyncio
async def test_agent_tool_call_flow(tmp_path):
    config = AppConfig()
    agent = Agent(config=config)
    test_file = str(tmp_path / "test.txt")
    first_response = LLMResponse(
        content="Let me check the file.",
        tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "filesystem", "arguments": {"action": "write", "path": test_file, "content": "hello"}},
        }],
    )
    second_response = LLMResponse(content="File written successfully!")
    agent._llm.chat = AsyncMock(side_effect=[first_response, second_response])
    events = await _collect_events(agent, "write a file")
    tool_call_events = [e for e in events if e.type == "tool_call"]
    tool_result_events = [e for e in events if e.type == "tool_result"]
    final_events = [e for e in events if e.type == "final_answer"]
    assert len(tool_call_events) >= 1
    assert len(tool_result_events) >= 1
    assert len(final_events) >= 1


@pytest.mark.asyncio
async def test_agent_safety_blocked():
    config = AppConfig(dangerous_commands=["rm -rf /"])
    agent = Agent(config=config)
    response = LLMResponse(
        content="Deleting everything.",
        tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "shell", "arguments": {"command": "rm -rf /"}},
        }],
    )
    agent._llm.chat = AsyncMock(return_value=response)
    events = await _collect_events(agent, "delete everything")
    blocked_events = [e for e in events if e.type == "tool_call" and e.blocked]
    assert len(blocked_events) >= 1


@pytest.mark.asyncio
async def test_agent_confirm_callback_allows():
    config = AppConfig(dangerous_commands=["del /s"])
    agent = Agent(config=config, confirm_callback=lambda name, args: True)
    response = LLMResponse(
        content="Deleting.",
        tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "shell", "arguments": {"command": "del /s C:\\temp"}},
        }],
    )
    second_response = LLMResponse(content="Done!")
    agent._llm.chat = AsyncMock(side_effect=[response, second_response])
    events = await _collect_events(agent, "delete temp")
    tool_call_events = [e for e in events if e.type == "tool_call" and not e.blocked]
    assert len(tool_call_events) >= 1


@pytest.mark.asyncio
async def test_agent_confirm_callback_denies():
    config = AppConfig(dangerous_commands=["del /s"])
    agent = Agent(config=config, confirm_callback=lambda name, args: False)
    response = LLMResponse(
        content="Deleting.",
        tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "shell", "arguments": {"command": "del /s C:\\temp"}},
        }],
    )
    second_response = LLMResponse(content="Operation was blocked.")
    agent._llm.chat = AsyncMock(side_effect=[response, second_response])
    events = await _collect_events(agent, "delete temp")
    blocked_events = [e for e in events if e.type == "tool_call" and e.blocked]
    assert len(blocked_events) >= 1


@pytest.mark.asyncio
async def test_agent_iteration_limit():
    config = AppConfig(max_iterations=2)
    agent = Agent(config=config)
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
async def test_agent_error_response():
    config = AppConfig()
    agent = Agent(config=config)
    agent._llm.chat = AsyncMock(return_value=LLMResponse(content="Connection failed", finish_reason="error"))
    events = await _collect_events(agent, "hello")
    error_events = [e for e in events if e.type == "error"]
    assert len(error_events) >= 1


@pytest.mark.asyncio
async def test_file_operations_e2e(tmp_path):
    fs_tool = FilesystemTool()
    file_path = str(tmp_path / "e2e_test.txt")
    write_result = await fs_tool.execute(action="write", path=file_path, content="initial content")
    assert write_result["success"] is True
    read_result = await fs_tool.execute(action="read", path=file_path)
    assert read_result["content"] == "initial content"
    write_result2 = await fs_tool.execute(action="write", path=file_path, content="modified content")
    assert write_result2["success"] is True
    read_result2 = await fs_tool.execute(action="read", path=file_path)
    assert read_result2["content"] == "modified content"
    delete_result = await fs_tool.execute(action="delete", path=file_path)
    assert delete_result["success"] is True
    exists_result = await fs_tool.execute(action="exists", path=file_path)
    assert exists_result["exists"] is False
