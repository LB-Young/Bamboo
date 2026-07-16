"""Tests for BKN CLI commands."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bamboo.run import app

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bkn" / "personal-media"


@pytest.fixture
def isolated_bkn_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home_dir = tmp_path / "home"
    bkn_dir = home_dir / ".bamboo" / "bkn"
    bkn_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    shutil.copytree(FIXTURE_ROOT, bkn_dir / "personal-media")
    return home_dir


def test_bkn_list_outputs_fixture_network(isolated_bkn_home: Path) -> None:
    result = CliRunner().invoke(app, ["bkn", "list"])

    assert result.exit_code == 0
    assert "personal-media" in result.output
    assert "content:agent-memory-design" not in result.output


def test_bkn_search_outputs_matches(isolated_bkn_home: Path) -> None:
    result = CliRunner().invoke(app, ["bkn", "search", "Agent Memory", "--network", "personal-media"])

    assert result.exit_code == 0
    assert '<bkn_results query="Agent Memory" network="personal-media" count="1">' in result.output
    assert "content:agent-memory-design" in result.output


def test_bkn_export_outputs_mermaid(isolated_bkn_home: Path) -> None:
    result = CliRunner().invoke(app, ["bkn", "export", "personal-media", "--node", "content:agent-memory-design"])

    assert result.exit_code == 0
    assert "flowchart LR" in result.output
    assert "content_agent_memory_design -->|PUBLISHED_ON| platform_github" in result.output


def test_bkn_validate_bad_fixture_returns_nonzero(isolated_bkn_home: Path) -> None:
    bad = isolated_bkn_home / ".bamboo" / "bkn" / "bad"
    bad.mkdir()
    (bad / "bkn.yaml").write_text("schema_version: 999\nname: bad\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["bkn", "validate"])

    assert result.exit_code == 1
    assert "error" in result.output
    assert "bad" in result.output
