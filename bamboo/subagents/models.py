"""Subagent definition models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WorkspaceMode = Literal["shared", "read_only", "tempdir", "worktree"]


@dataclass(frozen=True, slots=True)
class SubagentDefinition:
    """A restricted agent profile."""

    name: str
    description: str
    model: str = ""
    tools: dict[str, str | bool] = field(default_factory=dict)
    permission: str = "read-only"
    workspace_mode: WorkspaceMode = "shared"
    keep_workspace_on_success: bool = False
    validation_warnings: tuple[str, ...] = ()
    source_path: str = ""
    source: str = "builtin"


@dataclass(frozen=True, slots=True)
class SubagentRunResult:
    """Result returned after running a subagent."""

    subagent_name: str
    task_id: str
    session_id: str
    output: str
    status: str
    workspace_mode: str = "shared"
    workspace_path: str = ""
    changed_files: tuple[str, ...] = ()
    diff_stat: str = ""
    diff_patch_path: str = ""
    merge_required: bool = False
    workspace_retained: bool = False
    workspace_note: str = ""
