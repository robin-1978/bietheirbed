from __future__ import annotations

import pytest

from pc_assistant.tools.application import ApplicationTool


class TestApplicationToolName:
    def test_name(self):
        t = ApplicationTool()
        assert t.name == "application"

    def test_schema(self):
        t = ApplicationTool()
        s = t.schema()
        assert s["name"] == "application"


class TestApplicationListRunning:
    @pytest.mark.asyncio
    async def test_list_running(self):
        t = ApplicationTool()
        result = await t.execute(action="list_running")
        assert "processes" in result
        assert len(result["processes"]) > 0


class TestApplicationKillNoPid:
    @pytest.mark.asyncio
    async def test_kill_no_pid(self):
        t = ApplicationTool()
        result = await t.execute(action="kill")
        assert "error" in result


class TestApplicationLaunch:
    @pytest.mark.asyncio
    async def test_launch_no_command(self):
        t = ApplicationTool()
        result = await t.execute(action="launch")
        assert "error" in result


class TestApplicationUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        t = ApplicationTool()
        result = await t.execute(action="unknown")
        assert "error" in result
