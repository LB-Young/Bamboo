"""Subagent registry tests."""

from __future__ import annotations

from pathlib import Path

from bamboo.subagents.registry import SubagentRegistry, load_subagent_definition


def test_load_subagent_definition_parses_tools(tmp_path: Path) -> None:
    path = tmp_path / "explorer.yaml"
    path.write_text(
        "name: explorer\n"
        "description: Explore code.\n"
        "model: test-model\n"
        "permission: read-only\n"
        "tools:\n"
        "  read: true\n"
        "  write: false\n"
        "  bash: read_only\n",
        encoding="utf-8",
    )

    definition = load_subagent_definition(path, source="test")

    assert definition.name == "explorer"
    assert definition.model == "test-model"
    assert definition.tools == {"read": True, "write": False, "bash": "read_only"}


def test_subagent_registry_project_overrides_builtin(tmp_path: Path) -> None:
    builtin_dir = tmp_path / "builtin"
    project_dir = tmp_path / "project"
    builtin_dir.mkdir()
    project_dir.mkdir()
    (builtin_dir / "explorer.yaml").write_text(
        "name: explorer\ndescription: Builtin.\ntools:\n  read: true\n",
        encoding="utf-8",
    )
    (project_dir / "explorer.yaml").write_text(
        "name: explorer\ndescription: Project.\ntools:\n  grep: true\n",
        encoding="utf-8",
    )

    registry = SubagentRegistry(subagent_dirs=[("builtin", builtin_dir), ("project", project_dir)])
    definition = registry.get("explorer")

    assert definition is not None
    assert definition.description == "Project."
    assert definition.source == "project"
    assert definition.tools == {"grep": True}


def test_builtin_subagent_profiles_are_available() -> None:
    registry = SubagentRegistry.for_project(None)
    names = set(registry.available_names())

    assert {"explorer", "planner", "verifier", "reviewer"}.issubset(names)
