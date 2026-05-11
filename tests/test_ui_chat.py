from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pc_assistant.config import AppConfig
from pc_assistant.agent import Agent, AgentEvent
from pc_assistant.ui.chat import ChatUI


class TestChatUIInit:
    def test_init(self):
        ui = ChatUI(config=AppConfig())
        assert ui._config is not None
        assert ui._agent is None
        assert ui._running is False

    def test_init_with_confirm_callback(self):
        cb = lambda t, d: True
        ui = ChatUI(config=AppConfig(), confirm_callback=cb)
        assert ui._confirm_callback is cb


class TestChatUIPrint:
    def test_print_tool_call(self, capsys):
        ui = ChatUI(config=AppConfig())
        ui._console = None
        ui._print_tool_call("filesystem", {"action": "read"})
        captured = capsys.readouterr()
        assert "filesystem" in captured.out

    def test_print_tool_result(self, capsys):
        ui = ChatUI(config=AppConfig())
        ui._console = None
        ui._print_tool_result("filesystem", "file contents")
        captured = capsys.readouterr()
        assert "filesystem" in captured.out

    def test_print_tool_result_error(self, capsys):
        ui = ChatUI(config=AppConfig())
        ui._console = None
        ui._print_tool_result("shell", "command failed", is_error=True)
        captured = capsys.readouterr()
        assert "shell" in captured.out

    def test_print_final_answer(self, capsys):
        ui = ChatUI(config=AppConfig())
        ui._console = None
        ui._print("Here is your answer")
        captured = capsys.readouterr()
        assert "Here is your answer" in captured.out

    def test_print_error(self, capsys):
        ui = ChatUI(config=AppConfig())
        ui._console = None
        ui._print_error("Something went wrong")
        captured = capsys.readouterr()
        assert "Something went wrong" in captured.out

    def test_print_warning(self, capsys):
        ui = ChatUI(config=AppConfig())
        ui._console = None
        ui._print_warning("Be careful")
        captured = capsys.readouterr()
        assert "Be careful" in captured.out

    def test_print_tool_result_truncation(self, capsys):
        ui = ChatUI(config=AppConfig())
        ui._console = None
        long_result = "x" * 1000
        ui._print_tool_result("tool", long_result)
        captured = capsys.readouterr()
        assert len(captured.out) < 500


class TestChatUICommands:
    def test_exit_command(self):
        ui = ChatUI(config=AppConfig())
        ui._running = True
        result = ui._handle_user_command("/exit")
        assert result is True
        assert ui._running is False

    def test_quit_command(self):
        ui = ChatUI(config=AppConfig())
        ui._running = True
        result = ui._handle_user_command("/quit")
        assert result is True
        assert ui._running is False

    def test_clear_command(self):
        ui = ChatUI(config=AppConfig())
        agent = Agent(config=AppConfig())
        ui._agent = agent
        result = ui._handle_user_command("/clear")
        assert result is True

    def test_clear_no_agent(self):
        ui = ChatUI(config=AppConfig())
        result = ui._handle_user_command("/clear")
        assert result is True

    def test_help_command(self):
        ui = ChatUI(config=AppConfig())
        result = ui._handle_user_command("/help")
        assert result is True

    def test_config_command(self):
        ui = ChatUI(config=AppConfig())
        result = ui._handle_user_command("/config")
        assert result is True

    def test_tools_command(self):
        ui = ChatUI(config=AppConfig())
        agent = Agent(config=AppConfig())
        ui._agent = agent
        result = ui._handle_user_command("/tools")
        assert result is True

    def test_tools_no_agent(self):
        ui = ChatUI(config=AppConfig())
        result = ui._handle_user_command("/tools")
        assert result is True

    def test_history_command(self):
        ui = ChatUI(config=AppConfig())
        agent = Agent(config=AppConfig())
        ui._agent = agent
        result = ui._handle_user_command("/history")
        assert result is True

    def test_history_no_agent(self):
        ui = ChatUI(config=AppConfig())
        result = ui._handle_user_command("/history")
        assert result is True

    def test_unknown_command(self):
        ui = ChatUI(config=AppConfig())
        result = ui._handle_user_command("/unknown")
        assert result is True


class TestChatUIProcessEvents:
    @pytest.mark.asyncio
    async def test_process_events_no_agent(self, capsys):
        ui = ChatUI(config=AppConfig())
        await ui._process_events("hello")
        captured = capsys.readouterr()
        assert "Agent not initialized" in captured.out or "not initialized" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_process_events_with_agent(self):
        ui = ChatUI(config=AppConfig())
        ui._console = None
        agent = Agent(config=AppConfig())
        agent._llm.chat = AsyncMock(return_value=AgentEvent(
            type="final_answer", content="Hello!"
        ).__class__(type="final_answer", content="Hello!"))
        from pc_assistant.llm_provider import LLMResponse
        agent._llm.chat = AsyncMock(return_value=LLMResponse(content="Hello!", finish_reason="stop"))
        ui._agent = agent
        await ui._process_events("hi")


class TestChatUIShowWelcome:
    def test_show_welcome(self, capsys):
        ui = ChatUI(config=AppConfig())
        ui._console = None
        ui._show_welcome()
        captured = capsys.readouterr()
        assert "PC Assistant" in captured.out or "assistant" in captured.out.lower()
