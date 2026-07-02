"""Subagent definition models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SubagentDefinition:
    """A restricted agent profile."""

    name: str
    description: str
    model: str = ""
    tools: dict[str, str | bool] = field(default_factory=dict)
    permission: str = "read-only"
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
