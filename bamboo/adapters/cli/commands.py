"""Shared command expansion helpers for CLI and Web adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from bamboo.commands import CommandRegistry, create_command_registry

SLASH_COMMAND_PATTERN = re.compile(r"^/([A-Za-z0-9][A-Za-z0-9_-]*)(?:\s+(.*))?$", re.DOTALL)


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
    match = SLASH_COMMAND_PATTERN.match(stripped)
    if match is None:
        return CommandExpansionResult(message=message)

    name = match.group(1)
    arguments = match.group(2) or ""

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
