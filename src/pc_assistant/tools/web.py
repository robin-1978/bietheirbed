from __future__ import annotations

from typing import Any

from pc_assistant.tools.base import ToolBase


class WebTool(ToolBase):
    name = "web"
    description = "Search the web and fetch web pages"

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
                    "max_results": {"type": "integer", "description": "Max search results (default 8)"},
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
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[... truncated, {len(text) - max_chars} chars omitted]"
        return {"content": text, "url": url, "status_code": resp.status_code}

    async def _search(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        query = kwargs.get("query", "")
        if not query:
            return {"error": "No query provided"}
        max_results = kwargs.get("max_results", 8)

        ddgs_result = await self._search_ddgs(query, max_results)
        if ddgs_result is not None:
            return ddgs_result

        return await self._search_http(query, max_results)

    async def _search_ddgs(self, query: str, max_results: int) -> dict[str, Any] | None:
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except ImportError:
            try:
                from duckduckgo_search import DDGS

                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
            except ImportError:
                return None
        except Exception:
            return None

        if not results:
            return {"results": [], "query": query, "message": "No results found"}

        formatted = []
        for r in results:
            formatted.append({
                "title": r.get("title", ""),
                "url": r.get("href", r.get("link", "")),
                "snippet": r.get("body", r.get("snippet", "")),
            })

        return {"results": formatted, "query": query, "count": len(formatted)}

    async def _search_http(self, query: str, max_results: int) -> dict[str, Any]:
        try:
            import httpx
            from urllib.parse import quote_plus

            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            }) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            return {"error": f"Search error: {e}", "query": query}

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            results = []
            for item in soup.select(".result"):
                if len(results) >= max_results:
                    break
                title_el = item.select_one(".result__title a, .result__a")
                snippet_el = item.select_one(".result__snippet")
                if title_el:
                    href = title_el.get("href", "")
                    if href.startswith("//"):
                        href = "https:" + href
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": href,
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                    })
        except ImportError:
            return {"error": "beautifulsoup4 not available for search", "query": query}

        return {"results": results, "query": query, "count": len(results)}
