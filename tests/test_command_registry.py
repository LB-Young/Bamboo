"""CommandRegistry tests."""

from __future__ import annotations

from pathlib import Path

from bamboo.commands import CommandRegistry, load_command_definition


def test_load_command_definition_parses_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "commit.md"
    path.write_text(
        "---\n"
        "description: Draft a commit message.\n"
        "model: local-model\n"
        "subtask: true\n"
        "---\n\n"
        "Use args: $ARGUMENTS\n",
        encoding="utf-8",
    )

    definition = load_command_definition(path, source="test")

    assert definition.name == "commit"
    assert definition.description == "Draft a commit message."
    assert definition.model == "local-model"
    assert definition.subtask is True
    assert definition.body == "Use args: $ARGUMENTS"


def test_command_registry_expands_arguments(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    (commands_dir / "changelog.md").write_text(
        "---\n"
        "description: Changelog.\n"
        "---\n\n"
        "Write changelog for $ARGUMENTS.\n",
        encoding="utf-8",
    )
    registry = CommandRegistry(command_dirs=[("test", commands_dir)])
    registry.refresh()

    expansion = registry.expand("changelog", "v1.2.3")

    assert expansion.content == "Write changelog for v1.2.3."
    assert expansion.definition.source == "test"


def test_command_registry_project_overrides_user_and_builtin(tmp_path: Path) -> None:
    builtin_dir = tmp_path / "builtin"
    user_dir = tmp_path / "user"
    project_dir = tmp_path / "project"
    for directory in (builtin_dir, user_dir, project_dir):
        directory.mkdir()
    (builtin_dir / "commit.md").write_text("builtin $ARGUMENTS", encoding="utf-8")
    (user_dir / "commit.md").write_text("user $ARGUMENTS", encoding="utf-8")
    (project_dir / "commit.md").write_text("project $ARGUMENTS", encoding="utf-8")

    registry = CommandRegistry(
        command_dirs=[
            ("builtin", builtin_dir),
            ("user", user_dir),
            ("project", project_dir),
        ]
    )

    expansion = registry.expand("commit", "args")

    assert expansion.content == "project args"
    assert expansion.definition.source == "project"
