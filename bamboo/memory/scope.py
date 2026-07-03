"""Memory scope helpers for chat and project source logs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bamboo.memory.get_memory_path import get_memory_dir, get_memory_dir_name

MemoryScopeKind = Literal["chat", "project"]


@dataclass(frozen=True, slots=True)
class MemoryScope:
    """Identifies the memory namespace used by one query/session."""

    kind: MemoryScopeKind
    root: Path
    project_hash: str = ""
    project_root: str = ""

    @classmethod
    def chat(cls) -> "MemoryScope":
        """Return the global chat memory scope."""
        return cls(kind="chat", root=get_memory_dir() / "dates")

    @classmethod
    def project(cls, project_root: str | Path) -> "MemoryScope":
        """Return the memory scope for one project path."""
        project_hash = get_memory_dir_name(project_root)
        return cls(
            kind="project",
            root=get_memory_dir() / "projects" / project_hash,
            project_hash=project_hash,
            project_root=str(Path(project_root).expanduser().resolve(strict=False)),
        )


def resolve_memory_scope(*, session_mode: str, project_root: str | Path) -> MemoryScope:
    """Resolve chat/project scope from a session mode value."""
    if session_mode == "project":
        return MemoryScope.project(project_root)
    return MemoryScope.chat()
