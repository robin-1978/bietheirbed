from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

import httpx
from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMResponse(BaseModel):
    content: str
    tool_calls: list[dict[str, Any]] = []
    finish_reason: str = ""
    usage: dict[str, Any] = {}


class StreamChunk(BaseModel):
    delta_content: str = ""
    delta_tool_calls: list[dict[str, Any]] = []
    finish_reason: str = ""


class LLMProvider:
    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8080",
        model_name: str = "",
        timeout: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._model_name = model_name
        self._timeout = timeout
        self._max_retries = max_retries

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                if method == "POST":
                    resp = await client.post(url, **kwargs)
                else:
                    resp = await client.get(url, **kwargs)
                resp.raise_for_status()
                return resp
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.PoolTimeout) as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = 0.5 * (2 ** attempt)
                    await asyncio.sleep(delay)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503, 504):
                    last_error = e
                    if attempt < self._max_retries - 1:
                        delay = 0.5 * (2 ** attempt)
                        await asyncio.sleep(delay)
                else:
                    raise
        raise last_error  # type: ignore[misc]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await self._request_with_retry(
                    client, "POST", f"{self._server_url}/v1/chat/completions", json=payload
                )
                data = resp.json()
        except httpx.HTTPError as e:
            return LLMResponse(content=f"LLM request failed: {e}", finish_reason="error")
        except Exception as e:
            return LLMResponse(content=f"LLM request failed: {e}", finish_reason="error")
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        raw_tool_calls = message.get("tool_calls", [])
        tool_calls = self._normalize_tool_calls(raw_tool_calls)
        finish_reason = choice.get("finish_reason", "")
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        accumulated_tool_calls: dict[int, dict[str, Any]] = {}
        last_finish_reason = ""

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self._server_url}/v1/chat/completions",
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if not line.startswith("data: "):
                            continue
                        data_str = line[len("data: "):]
                        if data_str == "[DONE]":
                            if accumulated_tool_calls:
                                final_tool_calls = list(accumulated_tool_calls.values())
                                for tc in final_tool_calls:
                                    if "function" in tc and isinstance(tc["function"].get("arguments"), str):
                                        try:
                                            tc["function"]["arguments"] = json.loads(tc["function"]["arguments"])
                                        except (json.JSONDecodeError, TypeError):
                                            pass
                                yield StreamChunk(
                                    delta_content="",
                                    delta_tool_calls=final_tool_calls,
                                    finish_reason=last_finish_reason,
                                )
                            else:
                                yield StreamChunk(
                                    delta_content="",
                                    delta_tool_calls=[],
                                    finish_reason=last_finish_reason,
                                )
                            return

                        try:
                            chunk_data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk_data.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        finish_reason = choices[0].get("finish_reason", "")
                        if finish_reason:
                            last_finish_reason = finish_reason

                        delta_content = delta.get("content", "") or ""

                        delta_tool_call_list = delta.get("tool_calls", [])
                        delta_tool_calls: list[dict[str, Any]] = []

                        for dtc in delta_tool_call_list:
                            idx = dtc.get("index", 0)
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": dtc.get("id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": "",
                                        "arguments": "",
                                    },
                                }
                            acc = accumulated_tool_calls[idx]
                            if dtc.get("id"):
                                acc["id"] = dtc["id"]
                            func_delta = dtc.get("function", {})
                            if func_delta.get("name"):
                                acc["function"]["name"] += func_delta["name"]
                            if func_delta.get("arguments"):
                                acc["function"]["arguments"] += func_delta["arguments"]

                        if delta_content or delta_tool_call_list:
                            yield StreamChunk(
                                delta_content=delta_content,
                                delta_tool_calls=delta_tool_calls,
                                finish_reason="",
                            )
        except httpx.HTTPError as e:
            yield StreamChunk(
                delta_content=f"LLM stream failed: {e}",
                delta_tool_calls=[],
                finish_reason="error",
            )
        except Exception as e:
            yield StreamChunk(
                delta_content=f"LLM stream failed: {e}",
                delta_tool_calls=[],
                finish_reason="error",
            )

    def _normalize_tool_calls(self, raw_tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for tc in raw_tool_calls:
            tc_copy = dict(tc)
            func = tc_copy.get("function", {})
            if isinstance(func, dict):
                args = func.get("arguments")
                if isinstance(args, str):
                    try:
                        func["arguments"] = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        func["arguments"] = {}
                elif args is None:
                    func["arguments"] = {}
            tc_copy["function"] = func
            normalized.append(tc_copy)
        return normalized

    @staticmethod
    def format_tool_result_message(tool_call_id: str, content: str) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._server_url}/v1/models")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False
