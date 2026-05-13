from __future__ import annotations

import asyncio
from typing import Any

from pc_assistant.tools.base import ToolBase


class TimerTool(ToolBase):
    name = "timer"
    description = "Set countdown timers and reminders"

    def __init__(self) -> None:
        self._active_timers: dict[str, asyncio.Task] = {}

    async def execute(self, **kwargs: Any) -> Any:
        action = kwargs.get("action", "set")
        if action == "set":
            return await self._set_timer(kwargs)
        elif action == "list":
            return self._list_timers()
        elif action == "cancel":
            return self._cancel_timer(kwargs)
        return {"error": f"Unknown action: {action}. Use 'set', 'list', or 'cancel'."}

    async def _set_timer(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        seconds = kwargs.get("seconds", 0)
        minutes = kwargs.get("minutes", 0)
        hours = kwargs.get("hours", 0)
        message = kwargs.get("message", "")
        total_seconds = int(seconds) + int(minutes) * 60 + int(hours) * 3600
        if total_seconds <= 0:
            return {"error": "Timer duration must be positive. Provide seconds, minutes, or hours."}
        if total_seconds > 86400:
            return {"error": "Timer cannot exceed 24 hours."}
        timer_id = f"timer_{len(self._active_timers) + 1}"
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds:
            parts.append(f"{seconds}s")
        duration_str = " ".join(parts)
        desc = f"Timer {timer_id}: {duration_str}"
        if message:
            desc += f" - {message}"
        return {
            "timer_id": timer_id,
            "duration_seconds": total_seconds,
            "duration": duration_str,
            "message": message,
            "description": f"{desc} set. Will notify after {duration_str}.",
        }

    def _list_timers(self) -> dict[str, Any]:
        if not self._active_timers:
            return {"timers": [], "message": "No active timers"}
        return {
            "timers": list(self._active_timers.keys()),
            "count": len(self._active_timers),
        }

    def _cancel_timer(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        timer_id = kwargs.get("timer_id", "")
        if timer_id in self._active_timers:
            task = self._active_timers.pop(timer_id)
            task.cancel()
            return {"cancelled": timer_id}
        return {"error": f"Timer {timer_id} not found"}

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["set", "list", "cancel"],
                        "description": "Action: 'set' to create timer, 'list' to see active timers, 'cancel' to stop a timer",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Hours for the timer",
                    },
                    "minutes": {
                        "type": "integer",
                        "description": "Minutes for the timer",
                    },
                    "seconds": {
                        "type": "integer",
                        "description": "Seconds for the timer",
                    },
                    "message": {
                        "type": "string",
                        "description": "Reminder message when timer ends",
                    },
                    "timer_id": {
                        "type": "string",
                        "description": "Timer ID to cancel (for 'cancel' action)",
                    },
                },
                "required": ["action"],
            },
        }
