"""Registry for workflow packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bamboo.userspace.userspace import get_userspace_dir
from bamboo.workflows.models import WorkflowDefinition, WorkflowRunSpec

PACKAGE_BUILTIN_WORKFLOWS_DIR = Path(__file__).resolve().parent / "buildin"


class WorkflowRegistry:
    """Scans builtin, user, and project workflow packages."""

    def __init__(self, *, workflow_dirs: list[tuple[str, Path]] | None = None) -> None:
        self.workflow_dirs = workflow_dirs or [
            ("builtin", PACKAGE_BUILTIN_WORKFLOWS_DIR),
            ("user", get_userspace_dir() / "workflows"),
        ]
        self._workflows: dict[str, WorkflowDefinition] = {}

    @classmethod
    def for_project(cls, project: str | Path | None = None) -> "WorkflowRegistry":
        """Create a registry with builtin, user, and optional project workflow dirs."""
        workflow_dirs = [
            ("builtin", PACKAGE_BUILTIN_WORKFLOWS_DIR),
            ("user", get_userspace_dir() / "workflows"),
        ]
        if project:
            workflow_dirs.append(("project", Path(project).expanduser() / ".bamboo" / "workflows"))
        return cls(workflow_dirs=workflow_dirs)

    def refresh(self) -> None:
        """Scan workflow dirs. Later sources override earlier sources."""
        workflows: dict[str, WorkflowDefinition] = {}
        for source, root in self.workflow_dirs:
            if not root.is_dir():
                continue
            for entry_path in sorted(root.glob("*/WORKFLOW.md")):
                definition = load_workflow_definition(entry_path, source=source)
                workflows[definition.name] = definition
        self._workflows = workflows

    def list(self) -> list[WorkflowDefinition]:
        """Return available workflow definitions."""
        if not self._workflows:
            self.refresh()
        return sorted(self._workflows.values(), key=lambda item: item.name)

    def get(self, name: str) -> WorkflowDefinition | None:
        """Return a workflow by name."""
        if not self._workflows:
            self.refresh()
        return self._workflows.get(name)

    def available_names(self) -> list[str]:
        """Return available workflow names."""
        return [definition.name for definition in self.list()]


def create_workflow_registry(project: str | Path | None = None) -> WorkflowRegistry:
    """Create and scan the default workflow registry."""
    registry = WorkflowRegistry.for_project(project)
    registry.refresh()
    return registry


def load_workflow_definition(path: Path, *, source: str) -> WorkflowDefinition:
    """Load one WORKFLOW.md file with YAML frontmatter."""
    frontmatter, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    name = str(frontmatter.get("name") or path.parent.name).strip()
    if not name:
        raise ValueError(f"Workflow name is empty: {path}")
    return WorkflowDefinition(
        name=name,
        description=str(frontmatter.get("description", "")).strip(),
        source=source,
        source_dir=path.parent,
        entry_path=path,
        body=body,
        dependencies=_string_list(frontmatter.get("dependencies", []), f"workflows.{name}.dependencies"),
        usage=str(frontmatter.get("usage", "")).strip(),
        run=_parse_run_spec(frontmatter.get("run", {}), name),
    )


def _parse_run_spec(value: Any, workflow_name: str) -> WorkflowRunSpec:
    if value in (None, ""):
        return WorkflowRunSpec()
    if not isinstance(value, dict):
        raise ValueError(f"workflows.{workflow_name}.run must be a mapping")
    command = str(value.get("command") or "").strip()
    script = str(value.get("script") or "").strip()
    if command and script:
        raise ValueError(f"workflows.{workflow_name}.run cannot define both command and script")
    timeout = _positive_int(value.get("timeout", 120), f"workflows.{workflow_name}.run.timeout")
    risk = str(value.get("risk") or "execute").strip()
    if risk not in {"read", "write", "network", "execute", "unknown"}:
        raise ValueError(f"workflows.{workflow_name}.run.risk must be read/write/network/execute/unknown")
    return WorkflowRunSpec(
        command=command,
        script=script,
        cwd=str(value.get("cwd") or ".").strip(),
        timeout=timeout,
        risk=risk,  # type: ignore[arg-type]
    )


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---\n"):
        return {}, content.strip()
    end_marker = "\n---\n"
    end = content.find(end_marker, 4)
    if end == -1:
        return {}, content.strip()
    raw_frontmatter = content[4:end]
    body = content[end + len(end_marker):].strip()
    data = yaml.safe_load(raw_frontmatter) or {}
    if not isinstance(data, dict):
        data = {}
    return data, body


def _string_list(value: Any, field_name: str) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return list(value)


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value
