"""CLI-facing helpers for Skill Hub operations."""

from __future__ import annotations

from pathlib import Path

from bamboo.skills.guard import format_scan_report, scan_skill
from bamboo.skills.hub import SkillHub, SkillInstallResult
from bamboo.skills.registry import create_skill_registry


def list_skills(*, include_inactive: bool = False) -> list[tuple[str, str, str, str, str]]:
    """Return skill rows for CLI rendering."""
    registry = create_skill_registry()
    rows: list[tuple[str, str, str, str, str]] = []
    for definition in registry.list(include_inactive=include_inactive):
        state = registry.store.load_state(definition.name)
        rows.append(
            (
                definition.name,
                state.status if state is not None else "unknown",
                state.health if state is not None else "unknown",
                definition.trust_level,
                definition.description,
            )
        )
    return rows


def install_skill(
    identifier: str,
    *,
    trust_level: str = "community",
    force: bool = False,
    overwrite: bool = False,
) -> SkillInstallResult:
    """Install a skill through SkillHub."""
    return SkillHub().install(identifier, trust_level=trust_level, force=force, overwrite=overwrite)


def scan_skill_path(path: Path) -> str:
    """Scan a local skill directory and return a formatted report."""
    return format_scan_report(scan_skill(path, source=str(path)))
