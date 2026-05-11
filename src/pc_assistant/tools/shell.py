from __future__ import annotations

import asyncio
from typing import Any

from pc_assistant.tools.base import ToolBase


class ShellTool(ToolBase):
    name = "shell"
    description = "Execute shell commands with timeout and safety checks"

    async def execute(self, **kwargs: Any) -> Any:
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout")
        cwd = kwargs.get("cwd")
        if not command:
            return {"error": "No command provided"}
        try:
            timeout_val = int(timeout) if timeout is not None else None
        except (ValueError, TypeError):
            timeout_val = None
        return await self._run(command, timeout_val, cwd)

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds"},
                    "cwd": {"type": "string", "description": "Working directory for command"},
                },
                "required": ["command"],
            },
        }

    async def _run(self, command: str, timeout: int | None, cwd: str | None) -> dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "error": f"Command timed out after {timeout}s",
                    "returncode": -1,
                }
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return {
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        except Exception as e:
            return {"error": str(e), "returncode": -1}
