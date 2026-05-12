from __future__ import annotations

from typing import Any

from pc_assistant.context.memory import UserMemory
from pc_assistant.tools.base import ToolBase


class MemoryTool(ToolBase):
    name = "memory"
    description = "Store, retrieve, search, or delete user preferences and personal information for long-term memory"

    def __init__(self, memory: UserMemory | None = None) -> None:
        self._memory = memory

    def set_memory(self, memory: UserMemory) -> None:
        self._memory = memory

    async def execute(self, **kwargs: Any) -> Any:
        if self._memory is None:
            return {"error": "Memory not initialized"}
        action = kwargs.get("action")
        handlers = {
            "store": self._store,
            "retrieve": self._retrieve,
            "search": self._search,
            "delete": self._delete,
        }
        handler = handlers.get(action)
        if handler is None:
            return {"error": f"Unknown memory action: {action}. Use store/retrieve/search/delete."}
        return handler(kwargs)

    def _store(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        key = kwargs.get("key", "")
        value = kwargs.get("value", "")
        category = kwargs.get("category", "general")
        if not key or not value:
            return {"error": "Both 'key' and 'value' are required for store action"}
        self._memory.store(key, value, category=category, source="llm")
        return {"success": True, "key": key, "value": value, "category": category}

    def _retrieve(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        key = kwargs.get("key", "")
        if not key:
            return {"error": "'key' is required for retrieve action"}
        item = self._memory.retrieve(key)
        if item is None:
            return {"found": False, "key": key}
        return {"found": True, "key": item.key, "value": item.value, "category": item.category}

    def _search(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        query = kwargs.get("key", "")
        if not query:
            return {"error": "'key' (search query) is required for search action"}
        results = self._memory.search(query, limit=5)
        return {
            "results": [
                {"key": r.key, "value": r.value, "category": r.category}
                for r in results
            ],
            "count": len(results),
        }

    def _delete(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        key = kwargs.get("key", "")
        if not key:
            return {"error": "'key' is required for delete action"}
        deleted = self._memory.delete(key)
        return {"deleted": deleted, "key": key}

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["store", "retrieve", "search", "delete"],
                    },
                    "key": {
                        "type": "string",
                        "description": "Memory key (e.g. 'location', 'name', 'preference_editor')",
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to store (required for store action)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category: identity, location, preference, workflow, instruction",
                    },
                },
                "required": ["action", "key"],
            },
        }
