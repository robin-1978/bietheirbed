from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from pc_assistant.platform_ import get_default_dangerous_commands, get_default_protected_paths


class AppConfig(BaseModel):
    llm_provider: str = "llamacpp"
    llm_server_url: str = "http://127.0.0.1:8080"
    llm_model_name: str = ""
    llm_api_key: str = ""
    llm_api_base: str = ""
    llm_temperature: float = 0.7
    llm_timeout: float = 120.0
    max_iterations: int = 8
    max_tokens: int = 1024
    shell_timeout: int = 30
    context_window_budget: int = 8192
    dangerous_commands: list[str] = Field(default_factory=get_default_dangerous_commands)
    protected_paths: list[str] = Field(default_factory=get_default_protected_paths)
    log_file: str = "logs/pc_assistant.json"
    working_directory: str = Field(default_factory=os.getcwd)

    def masked_api_key(self) -> str:
        if not self.llm_api_key or len(self.llm_api_key) < 8:
            return "***" if self.llm_api_key else ""
        return self.llm_api_key[:4] + "****" + self.llm_api_key[-4:]

    def set_field(self, field_name: str, value: str) -> bool:
        type_map: dict[str, type] = {
            "llm_provider": str, "llm_server_url": str, "llm_model_name": str,
            "llm_api_key": str, "llm_api_base": str,
            "llm_temperature": float, "llm_timeout": float,
            "max_iterations": int, "max_tokens": int, "shell_timeout": int,
            "context_window_budget": int, "log_file": str, "working_directory": str,
        }
        if field_name not in type_map:
            return False
        try:
            setattr(self, field_name, type_map[field_name](value))
            return True
        except (ValueError, TypeError):
            return False


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def _env_overrides() -> dict[str, Any]:
    mapping: dict[str, tuple[str, type]] = {
        "PC_LLM_PROVIDER": ("llm_provider", str),
        "PC_LLM_SERVER_URL": ("llm_server_url", str),
        "PC_LLM_MODEL_NAME": ("llm_model_name", str),
        "PC_LLM_API_KEY": ("llm_api_key", str),
        "PC_LLM_API_BASE": ("llm_api_base", str),
        "PC_LLM_TEMPERATURE": ("llm_temperature", float),
        "PC_LLM_TIMEOUT": ("llm_timeout", float),
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
