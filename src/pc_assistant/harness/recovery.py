from __future__ import annotations

import traceback
from typing import Any, Callable, Awaitable


class RecoveryManager:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._error_log: list[dict[str, Any]] = []

    async def execute_with_recovery(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                self._error_log.append({
                    "attempt": attempt + 1,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc(),
                })
                if attempt < self._max_retries:
                    import asyncio

                    delay = self._base_delay * (2**attempt)
                    await asyncio.sleep(delay)
        raise last_error

    def get_error_log(self) -> list[dict[str, Any]]:
        return list(self._error_log)

    def clear_error_log(self) -> None:
        self._error_log.clear()
