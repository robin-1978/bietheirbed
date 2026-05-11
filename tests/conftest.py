from __future__ import annotations

import pytest


@pytest.fixture
def tmp_config(tmp_path):
    from pc_assistant.config import AppConfig

    return AppConfig()
