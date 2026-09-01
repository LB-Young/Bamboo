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
    marker.write_text("keep me", encoding="utf-8")
    env_file = bamboo_dir / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=keep-me\n", encoding="utf-8")
    user_skill = bamboo_dir / "skills" / "custom-skill" / "SKILL.md"
    user_skill.parent.mkdir(parents=True)
    user_skill.write_text("# Custom Skill\n", encoding="utf-8")
    memory_file = bamboo_dir / "memory" / "dates" / "chat" / "knowledge" / "profile.md"
    memory_file.parent.mkdir(parents=True)
    memory_file.write_text("# User Profile\n", encoding="utf-8")
    project_memory_file = bamboo_dir / "memory" / "projects" / "knowledge" / "overview.md"
    project_memory_file.parent.mkdir(parents=True)
    project_memory_file.write_text("# Project Memory\n", encoding="utf-8")
    session_log = bamboo_dir / "memory" / "dates" / "2026-09-01" / "session-a" / "messages.jsonl"
    session_log.parent.mkdir(parents=True)
    session_log.write_text('{"role":"user","content":"keep"}\n', encoding="utf-8")
    storage_file = bamboo_dir / "storage" / "skills" / "custom-skill" / "state.json"
    storage_file.parent.mkdir(parents=True)
    storage_file.write_text('{"enabled": true}\n', encoding="utf-8")
    bkn_file = bamboo_dir / "bkn" / "platforms" / "custom" / "preview.md"
    bkn_file.parent.mkdir(parents=True)
    bkn_file.write_text("# Custom BKN\n", encoding="utf-8")
    stale_builtin = bamboo_dir / "buildin_skills" / "stale" / "SKILL.md"
    stale_builtin.parent.mkdir(parents=True)
    stale_builtin.write_text("# Stale Builtin\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["init"], input="y\n")

    assert result.exit_code == 0
    assert "用户目录已就绪" in result.output
    assert marker.read_text(encoding="utf-8") == "keep me"
    assert env_file.read_text(encoding="utf-8") == "DEEPSEEK_API_KEY=keep-me\n"
    assert user_skill.read_text(encoding="utf-8") == "# Custom Skill\n"
    assert memory_file.read_text(encoding="utf-8") == "# User Profile\n"
    assert project_memory_file.read_text(encoding="utf-8") == "# Project Memory\n"
    assert session_log.read_text(encoding="utf-8") == '{"role":"user","content":"keep"}\n'
    assert storage_file.read_text(encoding="utf-8") == '{"enabled": true}\n'
    assert bkn_file.read_text(encoding="utf-8") == "# Custom BKN\n"
    assert not stale_builtin.exists()
    assert (bamboo_dir / "configs").is_dir()
    assert (bamboo_dir / ".env").is_file()
    assert (bamboo_dir / "cron" / "jobs.yaml").is_file()
    assert (bamboo_dir / "buildin_skills" / "skill-creator" / "SKILL.md").is_file()
