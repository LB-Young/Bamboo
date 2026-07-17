"""Command adapter expansion tests."""

from __future__ import annotations

from pathlib import Path

from bamboo.adapters.cli.commands import expand_command_message
from bamboo.commands import CommandRegistry


def test_expand_command_message_leaves_regular_message_unchanged(tmp_path: Path) -> None:
    registry = CommandRegistry(command_dirs=[("test", tmp_path)])

    result = expand_command_message("hello", registry=registry)

    assert result.expanded is False
    assert result.message == "hello"


def test_expand_command_message_leaves_absolute_path_message_unchanged(tmp_path: Path) -> None:
    registry = CommandRegistry(command_dirs=[("test", tmp_path)])
    message = "/Users/liubaoyang/Documents/project/script.py为这个脚本逐行添加注释，注释写在代码后面不要另起一行"

    result = expand_command_message(message, registry=registry)

    assert result.expanded is False
    assert result.command_name == ""
    assert result.error == ""
    assert result.message == message


def test_expand_command_message_leaves_plain_absolute_path_unchanged(tmp_path: Path) -> None:
    registry = CommandRegistry(command_dirs=[("test", tmp_path)])
    message = "/Users/liubaoyang/Documents/project/script.py"

    result = expand_command_message(message, registry=registry)

    assert result.expanded is False
    assert result.command_name == ""
    assert result.error == ""
    assert result.message == message


def test_expand_command_message_expands_slash_command(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    (commands_dir / "commit.md").write_text(
        "---\n"
        "description: Commit.\n"
        "---\n\n"
        "Draft commit for $ARGUMENTS.\n",
        encoding="utf-8",
    )
    registry = CommandRegistry(command_dirs=[("test", commands_dir)])

    result = expand_command_message("/commit skill hub", registry=registry)

    assert result.expanded is True
    assert result.command_name == "commit"
    assert result.message == "Draft commit for skill hub."


def test_expand_command_message_reports_missing_command(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    (commands_dir / "known.md").write_text("Known command.", encoding="utf-8")
    registry = CommandRegistry(command_dirs=[("test", commands_dir)])

    result = expand_command_message("/missing args", registry=registry)

    assert result.expanded is False
    assert result.command_name == "missing"
    assert "Command not found" in result.error
    assert result.available_commands == ["known"]
