"""Tests for dialog-facing skill/workflow installer tools."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from bamboo.tools.buildin.package_install import SkillInstallTool, WorkflowInstallTool
from bamboo.workflows.installer import WorkflowInstaller


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


@pytest.mark.asyncio
async def test_skill_installer_tool_installs_zip_package(tmp_path: Path) -> None:
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Demo skill.\n---\n# Demo\n",
        encoding="utf-8",
    )
    archive = tmp_path / "demo-skill.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(skill_dir / "SKILL.md", "demo-skill/SKILL.md")

    result = await SkillInstallTool().execute(str(archive), overwrite=True)

    assert result.success is True
    assert result.metadata is not None
    assert result.metadata["skill_name"] == "demo-skill"
    assert (tmp_path / "home" / ".bamboo" / "skills" / "demo-skill" / "SKILL.md").is_file()


@pytest.mark.asyncio
async def test_workflow_installer_tool_installs_directory(tmp_path: Path) -> None:
    workflow_dir = tmp_path / "demo-workflow"
    workflow_dir.mkdir()
    (workflow_dir / "WORKFLOW.md").write_text(
        "---\nname: demo-workflow\nrun:\n  command: \"printf ok\"\n---\n# Demo\n",
        encoding="utf-8",
    )
    install_dir = tmp_path / "installed-workflows"

    result = await WorkflowInstallTool(installer=WorkflowInstaller(workflows_dir=install_dir)).execute(str(workflow_dir))

    assert result.success is True
    assert result.metadata is not None
    assert result.metadata["workflow_name"] == "demo-workflow"
    assert (install_dir / "demo-workflow" / "WORKFLOW.md").is_file()


@pytest.mark.asyncio
async def test_workflow_installer_tool_installs_zip_package(tmp_path: Path) -> None:
    workflow_dir = tmp_path / "zip-workflow"
    workflow_dir.mkdir()
    (workflow_dir / "WORKFLOW.md").write_text(
        "---\nname: zip-workflow\nrun:\n  command: \"printf ok\"\n---\n# Zip Workflow\n",
        encoding="utf-8",
    )
    archive = tmp_path / "zip-workflow.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(workflow_dir / "WORKFLOW.md", "zip-workflow/WORKFLOW.md")
    install_dir = tmp_path / "installed-workflows"

    result = await WorkflowInstallTool(installer=WorkflowInstaller(workflows_dir=install_dir)).execute(str(archive))

    assert result.success is True
    assert result.metadata is not None
    assert result.metadata["workflow_name"] == "zip-workflow"
    assert (install_dir / "zip-workflow" / "WORKFLOW.md").is_file()


@pytest.mark.asyncio
async def test_workflow_installer_tool_blocks_dangerous_workflow(tmp_path: Path) -> None:
    workflow_dir = tmp_path / "danger-workflow"
    workflow_dir.mkdir()
    (workflow_dir / "WORKFLOW.md").write_text(
        "---\nname: danger-workflow\nrun:\n  command: \"rm -rf /\"\n---\n# Danger\n",
        encoding="utf-8",
    )
    install_dir = tmp_path / "installed-workflows"

    result = await WorkflowInstallTool(installer=WorkflowInstaller(workflows_dir=install_dir)).execute(str(workflow_dir))

    assert result.success is False
    assert result.metadata is not None
    assert result.metadata["scan_level"] == "dangerous"
    assert not (install_dir / "danger-workflow").exists()
