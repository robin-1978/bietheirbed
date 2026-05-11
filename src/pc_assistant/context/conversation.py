from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ConversationManager:
    def __init__(self, max_messages: int = 100) -> None:
        self._messages: list[Message] = []
        self._max_messages = max_messages

    def add(self, role: str, content: str, **kwargs: Any) -> Message:
        msg = Message(role=role, content=content, **kwargs)
        self._messages.append(msg)
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]
        return msg

    def add_user(self, content: str) -> Message:
        return self.add("user", content)

    def add_assistant(self, content: str, tool_calls: list[dict[str, Any]] | None = None) -> Message:
        return self.add("assistant", content, tool_calls=tool_calls)

    def add_tool_result(self, tool_call_id: str, content: str) -> Message:
        return self.add("tool", content, tool_call_id=tool_call_id)

    def get_messages(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in self._messages:
            d: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls is not None:
                d["tool_calls"] = msg.tool_calls
            if msg.tool_call_id is not None:
                d["tool_call_id"] = msg.tool_call_id
            result.append(d)
        return result

    def get_messages_for_llm(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in self._messages:
            if msg.role == "system":
                result.append({"role": "system", "content": msg.content})
            elif msg.role == "user":
                result.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                d: dict[str, Any] = {"role": "assistant", "content": msg.content}
                if msg.tool_calls is not None:
                    d["tool_calls"] = msg.tool_calls
                result.append(d)
            elif msg.role == "tool":
                result.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id or "",
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def summarize_old_messages(self, keep_recent: int = 10) -> None:
        if len(self._messages) <= keep_recent:
            return
        old_messages = self._messages[:-keep_recent]
        recent_messages = self._messages[-keep_recent:]
        summary_parts: list[str] = []
        for msg in old_messages:
            snippet = msg.content[:200]
            summary_parts.append(f"[{msg.role}] {snippet}")
        summary = "Summary of earlier conversation:\n" + "\n".join(summary_parts)
        summary_msg = Message(role="system", content=summary)
        self._messages = [summary_msg] + recent_messages

    def estimate_token_count(self) -> int:
        total = 0
        for msg in self._messages:
            total += max(1, len(msg.content) // 4)
            if msg.tool_calls is not None:
                for tc in msg.tool_calls:
                    total += max(1, len(str(tc)) // 4)
        return total

    def clear(self) -> None:
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)
