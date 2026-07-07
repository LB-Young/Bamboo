"""Tests for Bamboo plugin manifest installer."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bamboo.plugins import PluginInstaller, load_plugin_manifest


def test_install_skill_only_plugin_writes_lock(tmp_path: Path) -> None:
    userspace = tmp_path / "home" / ".bamboo"
    plugin_dir = _plugin_root(tmp_path, "skill-plugin")
    _write_manifest(plugin_dir, skills=[{"path": "skills/demo"}])
    _write_skill(plugin_dir / "skills" / "demo")

    result = PluginInstaller(userspace_dir=userspace).install(plugin_dir)

    assert result.installed is True
    assert (userspace / "skills" / "demo" / "SKILL.md").is_file()
    assert result.lock_entry is not None
    assert result.lock_entry.name == "skill-plugin"
    assert len(result.lock_entry.files) == 1
    assert (userspace / "storage" / "plugins" / "lock.json").is_file()


def test_install_combined_plugin_copies_command_workflow_and_mcp(tmp_path: Path) -> None:
    userspace = tmp_path / "home" / ".bamboo"
    plugin_dir = _plugin_root(tmp_path, "combo")
    _write_manifest(
        plugin_dir,
        skills=[{"path": "skills/demo"}],
        commands=[{"path": "commands/review.md"}],
        workflows=[{"path": "workflows/check"}],
        mcp={"path": "mcp.yaml"},
    )
    _write_skill(plugin_dir / "skills" / "demo")
    (plugin_dir / "commands").mkdir()
    (plugin_dir / "commands" / "review.md").write_text("---\nname: review\n---\nReview $ARGUMENTS\n", encoding="utf-8")
    workflow_dir = plugin_dir / "workflows" / "check"
    (workflow_dir / "scripts").mkdir(parents=True)
    (workflow_dir / "WORKFLOW.md").write_text("---\nname: check\nrun:\n  command: \"echo ok\"\n---\n# Check\n", encoding="utf-8")
    (workflow_dir / "scripts" / "check.sh").write_text("echo ok\n", encoding="utf-8")
    (plugin_dir / "mcp.yaml").write_text("mcp:\n  auto_start: false\n  servers: {}\n", encoding="utf-8")

    result = PluginInstaller(userspace_dir=userspace).install(plugin_dir)

    assert result.installed is True
    assert (userspace / "skills" / "demo" / "SKILL.md").is_file()
    assert (userspace / "commands" / "review.md").is_file()
    assert (userspace / "workflows" / "check" / "WORKFLOW.md").is_file()
    assert (userspace / "configs" / "mcp.d" / "combo.yaml").is_file()
    assert result.lock_entry is not None
    assert {file.component_type for file in result.lock_entry.files} == {"skill", "command", "workflow", "mcp"}


def test_dangerous_plugin_is_blocked_without_force(tmp_path: Path) -> None:
    userspace = tmp_path / "home" / ".bamboo"
    plugin_dir = _plugin_root(tmp_path, "danger")
    _write_manifest(plugin_dir, workflows=[{"path": "workflows/danger"}])
    workflow_dir = plugin_dir / "workflows" / "danger"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "WORKFLOW.md").write_text(
        "---\nname: danger\nrun:\n  command: \"rm -rf /\"\n---\n# Danger\n",
        encoding="utf-8",
    )

    result = PluginInstaller(userspace_dir=userspace).install(plugin_dir)

    assert result.installed is False
    assert result.scan_result.level == "dangerous"
    assert not (userspace / "workflows" / "danger").exists()


def test_remove_keeps_user_modified_files_by_default(tmp_path: Path) -> None:
    userspace = tmp_path / "home" / ".bamboo"
    plugin_dir = _plugin_root(tmp_path, "remove-demo")
    _write_manifest(plugin_dir, commands=[{"path": "commands/demo.md"}])
    (plugin_dir / "commands").mkdir()
    (plugin_dir / "commands" / "demo.md").write_text("demo\n", encoding="utf-8")
    installer = PluginInstaller(userspace_dir=userspace)
    install_result = installer.install(plugin_dir)
    assert install_result.installed is True
    target = userspace / "commands" / "demo.md"
    target.write_text("user modified\n", encoding="utf-8")

    remove_result = installer.remove("remove-demo")

    assert remove_result.removed is False
    assert str(target) in remove_result.kept_files
    assert target.is_file()
    assert installer.show("remove-demo") is not None

    forced = installer.remove("remove-demo", force=True)
    assert forced.removed is True
    assert not target.exists()
    assert installer.show("remove-demo") is None


def test_manifest_rejects_path_escape(tmp_path: Path) -> None:
    plugin_dir = _plugin_root(tmp_path, "escape")
    _write_manifest(plugin_dir, commands=[{"path": "../outside.md"}])

    with pytest.raises(ValueError, match="escapes plugin directory"):
        load_plugin_manifest(plugin_dir)


def _plugin_root(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    root.mkdir()
    return root


def _write_manifest(
    plugin_dir: Path,
    *,
    name: str | None = None,
    skills: list[dict[str, str]] | None = None,
    commands: list[dict[str, str]] | None = None,
    workflows: list[dict[str, str]] | None = None,
    mcp: dict[str, str] | None = None,
) -> None:
    data = {
        "name": name or plugin_dir.name,
        "version": "0.1.0",
        "description": "Demo plugin",
        "publisher": "test",
    }
    if skills is not None:
        data["skills"] = skills
    if commands is not None:
        data["commands"] = commands
    if workflows is not None:
        data["workflows"] = workflows
    if mcp is not None:
        data["mcp"] = mcp
    (plugin_dir / "bamboo-plugin.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _write_skill(skill_dir: Path) -> None:
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n# Demo\n", encoding="utf-8")
