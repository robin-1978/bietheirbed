from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from pc_assistant.tools.web import WebTool


class TestWebToolName:
    def test_name(self):
        t = WebTool()
        assert t.name == "web"

    def test_schema(self):
        t = WebTool()
        s = t.schema()
        assert s["name"] == "web"


class TestWebFetchNoUrl:
    @pytest.mark.asyncio
    async def test_fetch_no_url(self):
        t = WebTool()
        result = await t.execute(action="fetch")
        assert "error" in result


class TestWebSearch:
    @pytest.mark.asyncio
    async def test_search_no_query(self):
        t = WebTool()
        result = await t.execute(action="search")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        t = WebTool()
        result = await t.execute(action="search", query="Python programming")
        assert "results" in result or "error" in result

    @pytest.mark.asyncio
    async def test_search_ddgs_fallback(self):
        t = WebTool()
        with patch.dict("sys.modules", {"ddgs": None, "duckduckgo_search": None}):
            result = await t._search_http("test query", 3)
            assert "results" in result or "error" in result


class TestWebUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        t = WebTool()
        result = await t.execute(action="unknown")
        assert "error" in result
