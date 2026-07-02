"""Command template models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    """A user-triggered prompt template."""

    name: str
    description: str
    source_path: str
    source: str
    model: str = ""
    subtask: bool = False
    body: str = ""


@dataclass(frozen=True, slots=True)
class CommandExpansion:
    """Expanded command prompt."""

    name: str
    arguments: str
    content: str
    definition: CommandDefinition
