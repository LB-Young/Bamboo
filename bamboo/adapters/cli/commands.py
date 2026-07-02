"""Shared command expansion helpers for CLI and Web adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bamboo.commands import CommandRegistry, create_command_registry


@dataclass(frozen=True, slots=True)
class CommandExpansionResult:
    """Result of attempting to expand a slash command."""

    message: str
    expanded: bool = False
    command_name: str = ""
    error: str = ""
    available_commands: list[str] = field(default_factory=list)


def expand_command_message(
    message: str,
    *,
    project: str | Path | None = None,
    registry: CommandRegistry | None = None,
) -> CommandExpansionResult:
    """Expand `/command args` into a regular user message."""
    stripped = message.strip()
    if not stripped.startswith("/") or stripped in {"/", "//"}:
        return CommandExpansionResult(message=message)

    command_text = stripped[1:]
    name, _, arguments = command_text.partition(" ")
    name = name.strip()
    if not name:
        return CommandExpansionResult(message=message)

    command_registry = registry or create_command_registry(project)
    try:
        expansion = command_registry.expand(name, arguments)
    except KeyError as exc:
        return CommandExpansionResult(
            message=message,
            command_name=name,
            error=str(exc),
            available_commands=command_registry.available_names(),
        )
    return CommandExpansionResult(
        message=expansion.content,
        expanded=True,
        command_name=name,
        available_commands=command_registry.available_names(),
    )
