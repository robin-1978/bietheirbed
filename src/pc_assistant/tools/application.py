from __future__ import annotations

import subprocess
from typing import Any

from pc_assistant.platform_ import get_platform
from pc_assistant.tools.base import ToolBase


class ApplicationTool(ToolBase):
    name = "application"
    description = "Launch, list, and manage desktop applications"

    async def execute(self, **kwargs: Any) -> Any:
        action = kwargs.get("action")
        handlers = {
            "launch": self._launch,
            "list_running": self._list_running,
            "kill": self._kill,
        }
        handler = handlers.get(action)
        if handler is None:
            return {"error": f"Unknown application action: {action}"}
        return handler(kwargs)

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["launch", "list_running", "kill"],
                    },
                    "command": {"type": "string", "description": "Command to launch application"},
                    "pid": {"type": "integer", "description": "Process ID to kill"},
                },
                "required": ["action"],
            },
        }

    def _launch(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        command = kwargs.get("command", "")
        if not command:
            return {"error": "No command provided for launch"}
        try:
            current = get_platform()
            if current == "windows":
                proc = subprocess.Popen(command, shell=True, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            elif current == "macos":
                proc = subprocess.Popen(["open", "-a", command] if not command.startswith("/") else [command], start_new_session=True)
            else:
                proc = subprocess.Popen(command, shell=True, start_new_session=True)
            return {"success": True, "pid": proc.pid}
        except Exception as e:
            return {"error": str(e)}

    def _list_running(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        try:
            import psutil

            procs = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
                try:
                    info = proc.info
                    procs.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return {"processes": procs, "count": len(procs)}
        except ImportError:
            return {"error": "psutil not installed"}

    def _kill(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        pid = kwargs.get("pid")
        if pid is None:
            return {"error": "No pid provided"}
        try:
            import psutil

            proc = psutil.Process(int(pid))
            proc.terminate()
            return {"success": True}
        except psutil.NoSuchProcess:
            return {"error": f"No process with pid {pid}"}
        except psutil.AccessDenied:
            return {"error": f"Access denied killing pid {pid}"}
        except Exception as e:
            return {"error": str(e)}
