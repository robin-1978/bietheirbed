from __future__ import annotations

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


class TestWebSearchNotImplemented:
    @pytest.mark.asyncio
    async def test_search_not_implemented(self):
        t = WebTool()
        result = await t.execute(action="search", query="test")
        assert "error" in result or "not implemented" in str(result).lower()


class TestWebSearchNoQuery:
    @pytest.mark.asyncio
    async def test_search_no_query(self):
        t = WebTool()
        result = await t.execute(action="search")
        assert "error" in result


class TestWebUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        t = WebTool()
        result = await t.execute(action="unknown")
        assert "error" in result
