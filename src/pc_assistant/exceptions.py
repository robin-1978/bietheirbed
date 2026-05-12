from __future__ import annotations


class PCAssistantError(Exception):
    """Base exception for all pc_assistant errors."""


class LLMError(PCAssistantError):
    """Error communicating with LLM provider."""


class LLMTimeoutError(LLMError):
    """LLM request timed out."""


class LLMConnectionError(LLMError):
    """Cannot connect to LLM server."""


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded."""


class ToolError(PCAssistantError):
    """Error executing a tool."""


class ToolNotFoundError(ToolError):
    """Requested tool does not exist in registry."""


class ToolExecutionError(ToolError):
    """Tool execution failed."""


class SafetyError(PCAssistantError):
    """Operation blocked by safety checker."""


class ContextError(PCAssistantError):
    """Context/truncation related error."""


class ConfigError(PCAssistantError):
    """Configuration error."""


class MemoryError(PCAssistantError):
    """Memory storage/retrieval error."""
