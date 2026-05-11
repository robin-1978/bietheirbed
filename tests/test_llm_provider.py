from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pc_assistant.llm_provider import LLMMessage, LLMProvider, LLMResponse, StreamChunk


class TestLLMMessage:
    def test_creation(self):
        m = LLMMessage(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"


class TestLLMResponse:
    def test_defaults(self):
        r = LLMResponse(content="hi")
        assert r.content == "hi"
        assert r.tool_calls == []
        assert r.finish_reason == ""
        assert r.usage == {}

    def test_with_tool_calls(self):
        tc = [{"id": "call_1", "function": {"name": "test", "arguments": {}}}]
        r = LLMResponse(content="", tool_calls=tc, finish_reason="tool_calls")
        assert len(r.tool_calls) == 1
        assert r.finish_reason == "tool_calls"


class TestStreamChunk:
    def test_defaults(self):
        c = StreamChunk()
        assert c.delta_content == ""
        assert c.delta_tool_calls == []
        assert c.finish_reason == ""

    def test_with_values(self):
        c = StreamChunk(delta_content="hello", finish_reason="stop")
        assert c.delta_content == "hello"
        assert c.finish_reason == "stop"


class TestLLMProvider:
    def test_init(self):
        p = LLMProvider(server_url="http://localhost:8080", model_name="qwen")
        assert p._server_url == "http://localhost:8080"
        assert p._model_name == "qwen"

    def test_trailing_slash_stripped(self):
        p = LLMProvider(server_url="http://localhost:8080/")
        assert p._server_url == "http://localhost:8080"

    def test_defaults(self):
        p = LLMProvider()
        assert p._server_url == "http://127.0.0.1:8080"
        assert p._timeout == 120.0
        assert p._max_retries == 3

    def test_normalize_tool_calls_string_args(self):
        p = LLMProvider()
        raw = [{"function": {"name": "test", "arguments": '{"key": "value"}'}}]
        result = p._normalize_tool_calls(raw)
        assert result[0]["function"]["arguments"] == {"key": "value"}

    def test_normalize_tool_calls_dict_args(self):
        p = LLMProvider()
        raw = [{"function": {"name": "test", "arguments": {"key": "value"}}}]
        result = p._normalize_tool_calls(raw)
        assert result[0]["function"]["arguments"] == {"key": "value"}

    def test_normalize_tool_calls_invalid_json(self):
        p = LLMProvider()
        raw = [{"function": {"name": "test", "arguments": "not json"}}]
        result = p._normalize_tool_calls(raw)
        assert result[0]["function"]["arguments"] == {}

    def test_normalize_tool_calls_none_args(self):
        p = LLMProvider()
        raw = [{"function": {"name": "test", "arguments": None}}]
        result = p._normalize_tool_calls(raw)
        assert result[0]["function"]["arguments"] == {}

    def test_normalize_tool_calls_empty(self):
        p = LLMProvider()
        result = p._normalize_tool_calls([])
        assert result == []

    def test_format_tool_result_message(self):
        msg = LLMProvider.format_tool_result_message("call_123", "result data")
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "call_123"
        assert msg["content"] == "result data"

    @pytest.mark.asyncio
    async def test_chat_success(self):
        p = LLMProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!", "tool_calls": []}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "__aenter__", return_value=MagicMock()) as mock_enter:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_enter.return_value = mock_client

            with patch.object(p, "_request_with_retry", return_value=mock_response):
                result = await p.chat([{"role": "user", "content": "hi"}])
                assert result.content == "Hello!"
                assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_chat_with_tools(self):
        p = LLMProvider()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(p, "_request_with_retry", return_value=mock_response):
            result = await p.chat(
                [{"role": "user", "content": "do something"}],
                tools=[{"type": "function", "function": {"name": "test", "parameters": {}}}],
            )
            assert len(result.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_chat_connection_error(self):
        p = LLMProvider()
        with patch.object(p, "_request_with_retry", side_effect=httpx.ConnectError("Connection refused")):
            result = await p.chat([{"role": "user", "content": "hi"}])
            assert result.finish_reason == "error"
            assert "failed" in result.content.lower()

    @pytest.mark.asyncio
    async def test_chat_generic_error(self):
        p = LLMProvider()
        with patch.object(p, "_request_with_retry", side_effect=RuntimeError("unexpected")):
            result = await p.chat([{"role": "user", "content": "hi"}])
            assert result.finish_reason == "error"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        p = LLMProvider()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(httpx.AsyncClient, "__aenter__", return_value=MagicMock()) as mock_enter:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_enter.return_value = mock_client

            result = await p.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        p = LLMProvider()
        with patch.object(httpx.AsyncClient, "__aenter__", side_effect=httpx.ConnectError("no")):
            result = await p.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_chat_stream_basic(self):
        p = LLMProvider()
        sse_lines = [
            'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":""}]}',
            'data: {"choices":[{"delta":{"content":" world"},"finish_reason":""}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
            'data: [DONE]',
        ]

        async def mock_aiter_lines():
            for line in sse_lines:
                yield line

        class MockStreamResponse:
            def raise_for_status(self):
                pass
            def aiter_lines(self):
                return mock_aiter_lines()
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            def stream(self, *args, **kwargs):
                return MockStreamResponse()

        with patch("pc_assistant.llm_provider.httpx.AsyncClient", return_value=MockClient()):
            chunks = []
            async for chunk in p.chat_stream([{"role": "user", "content": "hi"}]):
                chunks.append(chunk)
            assert any(c.delta_content for c in chunks)

    @pytest.mark.asyncio
    async def test_chat_stream_with_tool_calls(self):
        p = LLMProvider()
        sse_lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"test","arguments":""}}]},"finish_reason":""}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"key\\": \\"val\\"}"}}]},"finish_reason":""}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
            'data: [DONE]',
        ]

        async def mock_aiter_lines():
            for line in sse_lines:
                yield line

        class MockStreamResponse:
            def raise_for_status(self):
                pass
            def aiter_lines(self):
                return mock_aiter_lines()
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            def stream(self, *args, **kwargs):
                return MockStreamResponse()

        with patch("pc_assistant.llm_provider.httpx.AsyncClient", return_value=MockClient()):
            chunks = []
            async for chunk in p.chat_stream([{"role": "user", "content": "do it"}]):
                chunks.append(chunk)
            final_chunks = [c for c in chunks if c.finish_reason == "tool_calls"]
            assert len(final_chunks) >= 1
            assert len(final_chunks[0].delta_tool_calls) >= 1

    @pytest.mark.asyncio
    async def test_chat_stream_error(self):
        p = LLMProvider()
        with patch.object(httpx.AsyncClient, "__aenter__", side_effect=httpx.ConnectError("fail")):
            chunks = []
            async for chunk in p.chat_stream([{"role": "user", "content": "hi"}]):
                chunks.append(chunk)
            assert len(chunks) >= 1
            assert chunks[0].finish_reason == "error"



