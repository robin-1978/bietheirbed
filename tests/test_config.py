from __future__ import annotations

import pytest
from pc_assistant.config import AppConfig


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.llm_provider == "llamacpp"
        assert cfg.llm_temperature == 0.7
        assert cfg.max_iterations == 8
        assert cfg.context_window_budget == 4096

    def test_masked_api_key_empty(self):
        cfg = AppConfig()
        assert cfg.masked_api_key() == ""

    def test_masked_api_key_short(self):
        cfg = AppConfig(llm_api_key="abc")
        assert cfg.masked_api_key() == "***"

    def test_masked_api_key_full(self):
        cfg = AppConfig(llm_api_key="sk-1234567890abcdef")
        result = cfg.masked_api_key()
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "****" in result

    def test_set_field_valid(self):
        cfg = AppConfig()
        assert cfg.set_field("llm_temperature", "0.9") is True
        assert cfg.llm_temperature == 0.9

    def test_set_field_invalid(self):
        cfg = AppConfig()
        assert cfg.set_field("llm_temperature", "not_a_number") is False

    def test_set_field_unknown(self):
        cfg = AppConfig()
        assert cfg.set_field("nonexistent_field", "value") is False

    def test_set_field_int(self):
        cfg = AppConfig()
        assert cfg.set_field("max_iterations", "16") is True
        assert cfg.max_iterations == 16

    def test_set_field_string(self):
        cfg = AppConfig()
        assert cfg.set_field("llm_model_name", "gpt-4") is True
        assert cfg.llm_model_name == "gpt-4"
