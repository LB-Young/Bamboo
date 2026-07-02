"""Registry for slash command prompt templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bamboo.commands.models import CommandDefinition, CommandExpansion
from bamboo.userspace.userspace import get_userspace_dir


PACKAGE_BUILTIN_COMMANDS_DIR = Path(__file__).resolve().parent / "buildin"


class CommandRegistry:
    """Scans and expands command templates."""

    def __init__(self, *, command_dirs: list[tuple[str, Path]] | None = None) -> None:
        self.command_dirs = command_dirs or [
            ("builtin", PACKAGE_BUILTIN_COMMANDS_DIR),
            ("user", get_userspace_dir() / "commands"),
        ]
        self._commands: dict[str, CommandDefinition] = {}

    @classmethod
    def for_project(cls, project: str | Path | None = None) -> "CommandRegistry":
        """Create a registry with builtin, user, and optional project commands."""
        command_dirs = [
            ("builtin", PACKAGE_BUILTIN_COMMANDS_DIR),
            ("user", get_userspace_dir() / "commands"),
        ]
        if project:
            command_dirs.append(("project", Path(project).expanduser() / ".bamboo" / "commands"))
        return cls(command_dirs=command_dirs)

    def refresh(self) -> None:
        """Scan command directories. Later sources override earlier sources."""
        commands: dict[str, CommandDefinition] = {}
        for source, root in self.command_dirs:
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.md")):
                definition = load_command_definition(path, source=source)
                commands[definition.name] = definition
        self._commands = commands

    def list(self) -> list[CommandDefinition]:
        """Return available command definitions."""
        if not self._commands:
            self.refresh()
        return sorted(self._commands.values(), key=lambda item: item.name)

    def get(self, name: str) -> CommandDefinition | None:
        """Return a command by name."""
        if not self._commands:
            self.refresh()
        return self._commands.get(name)

    def available_names(self) -> list[str]:
        """Return available command names."""
        return [definition.name for definition in self.list()]

    def expand(self, name: str, arguments: str = "") -> CommandExpansion:
        """Expand a command template with arguments."""
        definition = self.get(name)
        if definition is None:
            available = ", ".join(self.available_names()) or "none"
            raise KeyError(f"Command not found: {name}. Available commands: {available}")
        content = definition.body.replace("$ARGUMENTS", arguments.strip())
        return CommandExpansion(name=name, arguments=arguments, content=content.strip(), definition=definition)


def create_command_registry(project: str | Path | None = None) -> CommandRegistry:
    """Create and scan the default command registry."""
    registry = CommandRegistry.for_project(project)
    registry.refresh()
    return registry


def load_command_definition(path: Path, *, source: str) -> CommandDefinition:
    """Load a markdown command definition."""
    frontmatter, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    name = str(frontmatter.get("name") or path.stem).strip().lstrip("/")
    if not name:
        raise ValueError(f"Command name is empty: {path}")
    return CommandDefinition(
        name=name,
        description=str(frontmatter.get("description", "")).strip(),
        source_path=str(path),
        source=source,
        model=str(frontmatter.get("model", "") or ""),
        subtask=bool(frontmatter.get("subtask", False)),
        body=body,
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
