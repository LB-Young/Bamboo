"""Tools for installing downloaded skill and workflow packages."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from bamboo.skills.cli import install_skill
from bamboo.skills.guard import format_scan_report
from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.workflows.installer import WorkflowInstaller, format_workflow_scan_report


class SkillInstallTool(Tool):
    """Install a downloaded Skill package from a local folder or zip archive."""

    name = "skill_installer"
    description = "Install a Bamboo skill from a local folder or .zip archive after scan and validation."
    risk_level = "write"
    tags = ("skill", "install", "write")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local skill folder or .zip archive path."},
                "trust_level": {
                    "type": "string",
                    "description": "Trust level for SkillHub: trusted/community/local.",
                    "enum": ["trusted", "community", "local"],
                },
                "force": {"type": "boolean", "description": "Allow install despite non-safe scan findings."},
                "overwrite": {"type": "boolean", "description": "Overwrite an existing skill with the same name."},
            },
            "required": ["path"],
        }

    async def execute(
        self,
        path: str,
        trust_level: str = "local",
        force: bool = False,
        overwrite: bool = False,
    ) -> ToolResult:
        try:
            return _with_resolved_package(
                Path(path),
                lambda package_path: _install_skill_package(
                    package_path,
                    trust_level=trust_level,
                    force=force,
                    overwrite=overwrite,
                ),
            )
        except Exception as exc:
            return ToolResult(content=f"Skill install failed: {exc}", success=False, error=str(exc))


class WorkflowInstallTool(Tool):
    """Install a downloaded Workflow package from a local folder or zip archive."""

    name = "workflow_installer"
    description = "Install a Bamboo workflow from a local folder or .zip archive after scan and validation."
    risk_level = "write"
    tags = ("workflow", "install", "write")

    def __init__(self, *, installer: WorkflowInstaller | None = None) -> None:
        self.installer = installer

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local workflow folder or .zip archive path."},
                "force": {"type": "boolean", "description": "Allow install despite dangerous scan findings."},
                "overwrite": {"type": "boolean", "description": "Overwrite an existing workflow with the same name."},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, force: bool = False, overwrite: bool = False) -> ToolResult:
        try:
            installer = self.installer or WorkflowInstaller()
            return _with_resolved_package(
                Path(path),
                lambda package_path: _install_workflow_package(
                    installer,
                    package_path,
                    force=force,
                    overwrite=overwrite,
                ),
            )
        except Exception as exc:
            return ToolResult(content=f"Workflow install failed: {exc}", success=False, error=str(exc))


def _install_skill_package(package_path: Path, *, trust_level: str, force: bool, overwrite: bool) -> ToolResult:
    result = install_skill(
        f"local:{package_path}",
        trust_level=trust_level,
        force=force,
        overwrite=overwrite,
    )
    content = format_scan_report(result.scan_result)
    if not result.installed:
        return ToolResult(
            content=f"{content}\n\nSkill install blocked: {result.reason}",
            success=False,
            error=result.reason,
            metadata={"skill_name": result.name, "scan_level": result.scan_result.level},
        )
    return ToolResult(
        content=f"{content}\n\nSkill installed: {result.name}\nDestination: {result.destination}",
        metadata={
            "skill_name": result.name,
            "destination": str(result.destination),
            "scan_level": result.scan_result.level,
        },
    )


def _install_workflow_package(
    installer: WorkflowInstaller,
    package_path: Path,
    *,
    force: bool,
    overwrite: bool,
) -> ToolResult:
    result = installer.install(package_path, force=force, overwrite=overwrite)
    content = format_workflow_scan_report(result.scan_result)
    if not result.installed:
        return ToolResult(
            content=f"{content}\n\nWorkflow install blocked: {result.reason}",
            success=False,
            error=result.reason,
            metadata={"workflow_name": result.name, "scan_level": result.scan_result.level},
        )
    return ToolResult(
        content=f"{content}\n\nWorkflow installed: {result.name}\nDestination: {result.destination}",
        metadata={
            "workflow_name": result.name,
            "destination": str(result.destination),
            "scan_level": result.scan_result.level,
        },
    )


def _with_resolved_package(path: Path, callback: Callable[[Path], ToolResult]) -> ToolResult:
    source = path.expanduser().resolve()
    if source.is_dir():
        return callback(_select_package_root(source))
    if source.is_file() and source.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="bamboo-install-") as temp_dir:
            extract_root = Path(temp_dir) / "package"
            _safe_extract_zip(source, extract_root)
            return callback(_select_package_root(extract_root))
    raise FileNotFoundError(f"package path must be a directory or .zip archive: {source}")


def _select_package_root(root: Path) -> Path:
    if (root / "SKILL.md").is_file() or (root / "WORKFLOW.md").is_file():
        return root
    children = [path for path in root.iterdir() if path.is_dir()]
    if len(children) == 1:
        child = children[0]
        if (child / "SKILL.md").is_file() or (child / "WORKFLOW.md").is_file():
            return child
    return root


def _safe_extract_zip(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError(f"zip entry escapes destination: {member.filename}")
        archive.extractall(destination)
