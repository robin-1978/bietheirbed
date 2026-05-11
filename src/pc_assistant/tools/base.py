from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolBase(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        ...

    @abstractmethod
    def schema(self) -> dict[str, Any]:
        ...

    def __repr__(self) -> str:
        return f"<Tool {self.name}>"
