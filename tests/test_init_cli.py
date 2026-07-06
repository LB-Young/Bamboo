"""CLI init behavior tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from bamboo.run import app


@pytest.fixture()
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    return home_dir


def test_init_asks_before_overwriting_existing_bamboo_dir(isolated_home: Path) -> None:
    bamboo_dir = isolated_home / ".bamboo"
    bamboo_dir.mkdir()
    marker = bamboo_dir / "marker.txt"
    marker.write_text("keep me", encoding="utf-8")

    result = CliRunner().invoke(app, ["init"], input="n\n")

    assert result.exit_code == 0
    assert "init cancelled" in result.output
    assert marker.read_text(encoding="utf-8") == "keep me"


def test_init_overwrites_existing_bamboo_dir_after_confirmation(isolated_home: Path) -> None:
    bamboo_dir = isolated_home / ".bamboo"
    bamboo_dir.mkdir()
    marker = bamboo_dir / "marker.txt"
    marker.write_text("remove me", encoding="utf-8")

    result = CliRunner().invoke(app, ["init"], input="y\n")

    assert result.exit_code == 0
    assert "用户目录已就绪" in result.output
    assert not marker.exists()
    assert (bamboo_dir / "configs").is_dir()
    assert (bamboo_dir / "cron" / "jobs.yaml").is_file()
