"""Cron management tool tests."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from bamboo.tools import create_tool_registry
from bamboo.tools.buildin.cron import CronAddTool, CronDisableTool, CronEnableTool, CronGetTool, CronListTool


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_cron_tools_add_list_get_disable_enable() -> None:
    async def run_test() -> None:
        added = await CronAddTool().execute(
            name="daily-report",
            schedule="0 9 * * *",
            prompt="生成日报",
            project="/tmp/demo",
        )
        listed = await CronListTool().execute()
        fetched = await CronGetTool().execute(name="daily-report")
        disabled = await CronDisableTool().execute(name="daily-report")
        enabled = await CronEnableTool().execute(name="daily-report")

        assert added.success
        assert "daily-report" in listed.content
        assert fetched.metadata["job"]["prompt"] == "生成日报"  # type: ignore[index]
        assert disabled.metadata["job"]["enabled"] is False  # type: ignore[index]
        assert enabled.metadata["job"]["enabled"] is True  # type: ignore[index]

    anyio.run(run_test)


def test_cron_add_rejects_invalid_schedule() -> None:
    async def run_test() -> None:
        result = await CronAddTool().execute(name="bad", schedule="bad", prompt="x")
        assert not result.success
        assert result.error == "invalid_schedule"

    anyio.run(run_test)


def test_builtin_registry_exposes_cron_tools() -> None:
    registry = create_tool_registry()

    assert registry.get("cron_add") is not None
    assert registry.get_metadata("cron_add").risk_level == "write"  # type: ignore[union-attr]
    assert registry.get_metadata("cron_list").risk_level == "read"  # type: ignore[union-attr]
