from __future__ import annotations

from typing import Any

from pc_assistant.tools.base import ToolBase


class WebTool(ToolBase):
    name = "web"
    description = "Fetch web pages and extract text content"

    async def execute(self, **kwargs: Any) -> Any:
        action = kwargs.get("action")
        handlers = {
            "fetch": self._fetch,
            "search": self._search,
        }
        handler = handlers.get(action)
        if handler is None:
            return {"error": f"Unknown web action: {action}"}
        return await handler(kwargs)

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["fetch", "search"],
                    },
                    "url": {"type": "string", "description": "URL to fetch"},
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["action"],
            },
        }

    async def _fetch(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        url = kwargs.get("url", "")
        if not url:
            return {"error": "No URL provided"}
        try:
            import httpx

            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except httpx.HTTPError as e:
            return {"error": f"HTTP error: {e}"}
        try:
            from bs4 import BeautifulSoup
            from markdownify import markdownify as md

            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = md(str(soup))
        except ImportError:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
        return {"content": text, "url": url, "status_code": resp.status_code}

    async def _search(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        query = kwargs.get("query", "")
        if not query:
            return {"error": "No query provided"}
        return {"error": "Search not yet implemented", "query": query}
