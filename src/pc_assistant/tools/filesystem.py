from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from pc_assistant.tools.base import ToolBase


_MAX_FILE_SIZE = 1_048_576


class FilesystemTool(ToolBase):
    name = "filesystem"
    description = "Read, write, list, and manage files and directories"

    async def execute(self, **kwargs: Any) -> Any:
        action = kwargs.get("action")
        path = kwargs.get("path", "")
        handlers = {
            "read": self._read,
            "write": self._write,
            "list": self._list,
            "mkdir": self._mkdir,
            "delete": self._delete,
            "copy": self._copy,
            "move": self._move,
            "exists": self._exists,
        }
        handler = handlers.get(action)
        if handler is None:
            return {"error": f"Unknown filesystem action: {action}"}
        return handler(path, kwargs)

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "list", "mkdir", "delete", "copy", "move", "exists"],
                    },
                    "path": {"type": "string", "description": "Target file or directory path"},
                    "content": {"type": "string", "description": "Content to write (for write action)"},
                    "destination": {"type": "string", "description": "Destination path (for copy/move)"},
                },
                "required": ["action", "path"],
            },
        }

    def _read(self, path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        try:
            p = Path(path)
            if not p.exists():
                return {"error": f"Path does not exist: {path}"}
            if p.is_dir():
                return {"error": f"Path is a directory, not a file: {path}"}
            file_size = p.stat().st_size
            if file_size > _MAX_FILE_SIZE:
                content = p.read_text(encoding="utf-8", errors="replace")[:_MAX_FILE_SIZE]
                return {"content": content, "size": file_size, "truncated": True, "max_size": _MAX_FILE_SIZE}
            content = p.read_text(encoding="utf-8")
            return {"content": content, "size": file_size}
        except Exception as e:
            return {"error": str(e)}

    def _write(self, path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        content = kwargs.get("content", "")
        try:
            content_bytes = content.encode("utf-8")
            if len(content_bytes) > _MAX_FILE_SIZE:
                return {"error": f"Content exceeds maximum size of {_MAX_FILE_SIZE} bytes"}
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {"success": True, "bytes_written": len(content_bytes)}
        except Exception as e:
            return {"error": str(e)}

    def _list(self, path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        try:
            p = Path(path)
            if not p.is_dir():
                return {"error": f"Path is not a directory: {path}"}
            entries = []
            for entry in sorted(p.iterdir()):
                entries.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else None,
                })
            return {"entries": entries, "count": len(entries)}
        except Exception as e:
            return {"error": str(e)}

    def _mkdir(self, path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def _delete(self, path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        try:
            p = Path(path)
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def _copy(self, path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        destination = kwargs.get("destination", "")
        try:
            src = Path(path)
            dst = Path(destination)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def _move(self, path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        destination = kwargs.get("destination", "")
        try:
            shutil.move(path, destination)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def _exists(self, path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        p = Path(path)
        return {"exists": p.exists(), "is_file": p.is_file(), "is_dir": p.is_dir()}
