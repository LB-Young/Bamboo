"""Registry for subagent profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bamboo.subagents.models import SubagentDefinition
from bamboo.userspace.userspace import get_userspace_dir


PACKAGE_BUILTIN_SUBAGENTS_DIR = Path(__file__).resolve().parent / "buildin"


class SubagentRegistry:
    """Scans builtin, user, and project subagent definitions."""

    def __init__(self, *, subagent_dirs: list[tuple[str, Path]] | None = None) -> None:
        self.subagent_dirs = subagent_dirs or [
            ("builtin", PACKAGE_BUILTIN_SUBAGENTS_DIR),
            ("user", get_userspace_dir() / "agents"),
        ]
        self._definitions: dict[str, SubagentDefinition] = {}

    @classmethod
    def for_project(cls, project: str | Path | None = None) -> "SubagentRegistry":
        dirs = [
            ("builtin", PACKAGE_BUILTIN_SUBAGENTS_DIR),
            ("user", get_userspace_dir() / "agents"),
        ]
        if project:
            dirs.append(("project", Path(project).expanduser() / ".bamboo" / "agents"))
        return cls(subagent_dirs=dirs)

    def refresh(self) -> None:
        """Scan profile files. Later sources override earlier sources."""
        definitions: dict[str, SubagentDefinition] = {}
        for source, root in self.subagent_dirs:
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.yaml")):
                definition = load_subagent_definition(path, source=source)
                definitions[definition.name] = definition
        self._definitions = definitions

    def list(self) -> list[SubagentDefinition]:
        """Return known subagent definitions."""
        if not self._definitions:
            self.refresh()
        return sorted(self._definitions.values(), key=lambda item: item.name)

    def get(self, name: str) -> SubagentDefinition | None:
        """Return a subagent definition by name."""
        if not self._definitions:
            self.refresh()
        return self._definitions.get(name)

    def available_names(self) -> list[str]:
        """Return known subagent names."""
        return [definition.name for definition in self.list()]


def create_subagent_registry(project: str | Path | None = None) -> SubagentRegistry:
    """Create and scan a subagent registry."""
    registry = SubagentRegistry.for_project(project)
    registry.refresh()
    return registry


def load_subagent_definition(path: Path, *, source: str) -> SubagentDefinition:
    """Load one YAML subagent profile."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Subagent profile must be a mapping: {path}")
    name = str(data.get("name") or path.stem).strip()
    if not name:
        raise ValueError(f"Subagent name is empty: {path}")
    tools = data.get("tools", {})
    if not isinstance(tools, dict):
        raise ValueError(f"Subagent tools must be a mapping: {path}")
    normalized_tools: dict[str, str | bool] = {}
    for tool_name, mode in tools.items():
        normalized_tools[str(tool_name)] = _normalize_tool_mode(mode)
    return SubagentDefinition(
        name=name,
        description=str(data.get("description", "")).strip(),
        model=str(data.get("model", "") or ""),
        tools=normalized_tools,
        permission=str(data.get("permission", "read-only") or "read-only"),
        source_path=str(path),
        source=source,
    )


def _normalize_tool_mode(value: Any) -> str | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "allow"}:
            return True
        if normalized in {"false", "no", "deny"}:
            return False
        return normalized
    return bool(value)
