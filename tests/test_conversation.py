from __future__ import annotations

import pytest

from pc_assistant.context.conversation import ConversationManager


class TestConversationManager:
    def test_add_user(self):
        cm = ConversationManager()
        cm.set_system_context("You are helpful.")
        msg = cm.add_user("Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_add_assistant(self):
        cm = ConversationManager()
        cm.set_system_context("You are helpful.")
        msg = cm.add_assistant("Hi there")
        assert msg.role == "assistant"

    def test_add_system_raises(self):
        cm = ConversationManager()
        with pytest.raises(ValueError, match="System messages"):
            cm.add("system", "test")

    def test_get_messages_for_llm(self):
        cm = ConversationManager()
        cm.set_system_context("Be helpful.")
        cm.add_user("hi")
        cm.add_assistant("hello")
        messages = cm.get_messages_for_llm()
        assert messages[0]["role"] == "system"
        assert len(messages) == 3

    def test_date_context_injected(self):
        cm = ConversationManager()
        cm.set_system_context("Be helpful.")
        cm.add_user("hi")
        messages = cm.get_messages_for_llm()
        system_content = messages[0]["content"]
        assert "Current date" in system_content

    def test_tool_result(self):
        cm = ConversationManager()
        cm.set_system_context("sys")
        cm.add_tool_result("tc1", "result text")
        messages = cm.get_messages_for_llm()
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "tc1"

    def test_clear(self):
        cm = ConversationManager()
        cm.set_system_context("sys")
        cm.add_user("hi")
        cm.clear()
        assert len(cm) == 0

    def test_max_messages(self):
        cm = ConversationManager(max_messages=5)
        cm.set_system_context("sys")
        for i in range(10):
            cm.add_user(f"msg {i}")
        assert len(cm) <= 5

    def test_estimate_token_count(self):
        cm = ConversationManager()
        cm.set_system_context("sys")
        cm.add_user("Hello world")
        count = cm.estimate_token_count()
        assert count > 0
