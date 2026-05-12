from __future__ import annotations

import pytest

from pc_assistant.exceptions import (
    PCAssistantError,
    LLMError,
    LLMTimeoutError,
    LLMConnectionError,
    LLMRateLimitError,
    ToolError,
    ToolNotFoundError,
    ToolExecutionError,
    SafetyError,
    ConfigError,
    MemoryError,
)


class TestExceptionHierarchy:
    def test_base_exception(self):
        with pytest.raises(PCAssistantError):
            raise PCAssistantError("test")

    def test_llm_error_hierarchy(self):
        assert issubclass(LLMError, PCAssistantError)
        assert issubclass(LLMTimeoutError, LLMError)
        assert issubclass(LLMConnectionError, LLMError)
        assert issubclass(LLMRateLimitError, LLMError)

    def test_tool_error_hierarchy(self):
        assert issubclass(ToolError, PCAssistantError)
        assert issubclass(ToolNotFoundError, ToolError)
        assert issubclass(ToolExecutionError, ToolError)

    def test_safety_error(self):
        assert issubclass(SafetyError, PCAssistantError)

    def test_config_error(self):
        assert issubclass(ConfigError, PCAssistantError)

    def test_memory_error(self):
        assert issubclass(MemoryError, PCAssistantError)

    def test_catch_base(self):
        try:
            raise LLMTimeoutError("timeout")
        except PCAssistantError as e:
            assert "timeout" in str(e)

    def test_catch_llm_base(self):
        try:
            raise LLMConnectionError("no connection")
        except LLMError as e:
            assert "no connection" in str(e)
