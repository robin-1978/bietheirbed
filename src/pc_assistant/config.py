from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    llm_server_url: str = "http://127.0.0.1:8080"
    llm_model_name: str = ""
    max_iterations: int = 15
    shell_timeout: int = 30
    context_window_budget: int = 4096
    dangerous_commands: list[str] = Field(
        default_factory=lambda: [
            "rm -rf /",
            "del /s /q C:\\",
            "format",
            "shutdown",
            "mkfs",
        ]
    )
    protected_paths: list[str] = Field(
        default_factory=lambda: [
            "/etc/passwd",
            "/etc/shadow",
            "C:\\Windows\\System32",
            "C:\\Windows\\SysWOW64",
        ]
    )
    log_file: str = "logs/pc_assistant.json"
    working_directory: str = Field(default_factory=os.getcwd)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def _env_overrides() -> dict[str, Any]:
    mapping: dict[str, tuple[str, type]] = {
        "PC_LLM_SERVER_URL": ("llm_server_url", str),
        "PC_LLM_MODEL_NAME": ("llm_model_name", str),
        "PC_MAX_ITERATIONS": ("max_iterations", int),
        "PC_SHELL_TIMEOUT": ("shell_timeout", int),
        "PC_CONTEXT_WINDOW_BUDGET": ("context_window_budget", int),
        "PC_LOG_FILE": ("log_file", str),
        "PC_WORKING_DIRECTORY": ("working_directory", str),
    }
    overrides: dict[str, Any] = {}
    for env_key, (field_name, field_type) in mapping.items():
        raw = os.environ.get(env_key)
        if raw is not None:
            try:
                overrides[field_name] = field_type(raw)
            except (ValueError, TypeError):
                pass
    raw_dangerous = os.environ.get("PC_DANGEROUS_COMMANDS")
    if raw_dangerous:
        overrides["dangerous_commands"] = [
            cmd.strip() for cmd in raw_dangerous.split(",") if cmd.strip()
        ]
    raw_protected = os.environ.get("PC_PROTECTED_PATHS")
    if raw_protected:
        overrides["protected_paths"] = [
            p.strip() for p in raw_protected.split(",") if p.strip()
        ]
    return overrides


def load_config(config_path: str | Path | None = None) -> AppConfig:
    if config_path is None:
        config_path = Path("config/default.yaml")
    else:
        config_path = Path(config_path)
    yaml_data = _load_yaml(config_path)
    env_data = _env_overrides()
    merged: dict[str, Any] = {**yaml_data, **env_data}
    return AppConfig(**merged)
