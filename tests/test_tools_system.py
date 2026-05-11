from __future__ import annotations

import pytest

from pc_assistant.tools.system import SystemTool


class TestSystemToolName:
    def test_name(self):
        t = SystemTool()
        assert t.name == "system"

    def test_schema(self):
        t = SystemTool()
        s = t.schema()
        assert s["name"] == "system"


class TestSystemInfo:
    @pytest.mark.asyncio
    async def test_info(self):
        t = SystemTool()
        result = await t.execute(action="info")
        assert "platform" in result
        assert "cpu_count" in result

    @pytest.mark.asyncio
    async def test_info_platform_details(self):
        t = SystemTool()
        result = await t.execute(action="info")
        assert result["platform"] is not None


class TestSystemDiskUsage:
    @pytest.mark.asyncio
    async def test_disk_usage(self):
        t = SystemTool()
        result = await t.execute(action="disk_usage")
        assert "disks" in result or "error" not in result


class TestSystemUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        t = SystemTool()
        result = await t.execute(action="unknown")
        assert "error" in result
