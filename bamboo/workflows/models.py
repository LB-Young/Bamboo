"""Workflow definition models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class WorkflowRunSpec:
    """Executable entry declared by WORKFLOW.md."""

    command: str = ""
    script: str = ""
    cwd: str = "."
    timeout: int = 120
    risk: Literal["read", "write", "network", "execute", "unknown"] = "execute"


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """A workflow package loaded from WORKFLOW.md."""

    name: str
    description: str
    source: str
    source_dir: Path
    entry_path: Path
    body: str
    dependencies: list[str] = field(default_factory=list)
    usage: str = ""
    run: WorkflowRunSpec = field(default_factory=WorkflowRunSpec)
