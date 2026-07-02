"""Shell command classification and conservative blocking rules."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum


class CommandRisk(str, Enum):
    """Coarse command risk categories used by permission policy."""

    READ_ONLY = "read_only"
    WRITE = "write"
    NETWORK = "network"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CommandSecurityResult:
    """Result of command security inspection."""

    allowed: bool
    risk: CommandRisk
    reason: str = ""
    requires_confirmation: bool = False


DESTRUCTIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|[;&|]\s*)rm\s+-[^\n]*[rf][^\n]*\s+(/|~|\$HOME)(\s|$)"),
    re.compile(r"(^|\s)rm\s+-[^\n]*r[^\n]*f\b"),
    re.compile(r"(^|\s)mkfs(\.|[\s/]|$)"),
    re.compile(r"(^|\s)dd\s+[^\n]*(of=/dev/|if=/dev/)"),
    re.compile(r"(^|\s):\(\)\s*\{"),
    re.compile(r"\b(curl|wget)\b[^\n|;]*\|\s*(sh|bash|zsh|python|python3)\b"),
    re.compile(r"(^|\s)git\s+reset\s+--hard\b"),
    re.compile(r"(^|\s)git\s+clean\s+[^\n]*-[^\n]*[fd][^\n]*(\s|$)"),
    re.compile(r"(^|\s)git\s+push\b[^\n]*(--force|-f)\b"),
    re.compile(r"(^|\s)chmod\s+(-R\s+)?777\s+(/|~|\$HOME)(\s|$)"),
    re.compile(r"(^|\s)chmod\s+[^\n]*\+s\b"),
    re.compile(r"(^|\s)chown\s+(-R\s+)?[^\n]+\s+(/|~|\$HOME)(\s|$)"),
    re.compile(r"(^|\s)>\s*(/etc/passwd|/etc/shadow|~/.ssh/authorized_keys|\$HOME/.ssh/authorized_keys)\b"),
)

NETWORK_COMMANDS = {
    "curl",
    "wget",
    "ssh",
    "scp",
    "sftp",
    "rsync",
    "nc",
    "netcat",
    "telnet",
    "ping",
    "dig",
    "nslookup",
    "host",
    "gh",
}

WRITE_COMMANDS = {
    "touch",
    "mkdir",
    "cp",
    "mv",
    "rm",
    "rmdir",
    "tee",
    "sed",
    "perl",
    "python",
    "python3",
    "node",
    "npm",
    "pnpm",
    "yarn",
    "pip",
    "pip3",
    "cargo",
    "go",
    "make",
    "chmod",
    "chown",
    "ln",
    "tar",
    "unzip",
    "zip",
}

READ_ONLY_COMMANDS = {
    "pwd",
    "ls",
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "grep",
    "rg",
    "find",
    "fd",
    "wc",
    "sort",
    "uniq",
    "cut",
    "awk",
    "sed",
    "jq",
    "yq",
    "which",
    "whereis",
    "whoami",
    "id",
    "uname",
    "date",
    "echo",
    "printf",
    "env",
    "printenv",
    "ps",
    "top",
    "df",
    "du",
    "stat",
    "file",
    "git",
}

WRITE_OPERATORS = (">", ">>", "2>", "2>>", "&>", "| tee")


def inspect_command(command: str) -> CommandSecurityResult:
    """Classify a shell command and reject clearly dangerous patterns."""
    normalized = command.strip()
    if not normalized:
        return CommandSecurityResult(False, CommandRisk.UNKNOWN, "empty command")

    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern.search(normalized):
            return CommandSecurityResult(
                False,
                CommandRisk.DESTRUCTIVE,
                f"matches destructive pattern: {pattern.pattern}",
                requires_confirmation=True,
            )

    if _has_write_operator(normalized):
        return CommandSecurityResult(True, CommandRisk.WRITE, "uses shell output redirection", True)

    commands = _extract_commands(normalized)
    if not commands:
        return CommandSecurityResult(True, CommandRisk.UNKNOWN, "unable to parse command", True)

    if any(command_name in NETWORK_COMMANDS for command_name in commands):
        return CommandSecurityResult(True, CommandRisk.NETWORK, "uses network-capable command", True)

    if commands[0] == "git":
        return _inspect_git(normalized)

    if any(command_name in WRITE_COMMANDS for command_name in commands):
        return CommandSecurityResult(True, CommandRisk.WRITE, "uses filesystem or process mutation command", True)

    if all(command_name in READ_ONLY_COMMANDS for command_name in commands):
        return CommandSecurityResult(True, CommandRisk.READ_ONLY, "read-only command")

    return CommandSecurityResult(True, CommandRisk.UNKNOWN, "unknown command risk", True)


def _has_write_operator(command: str) -> bool:
    return any(operator in command for operator in WRITE_OPERATORS)


def _extract_commands(command: str) -> list[str]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return []

    commands: list[str] = []
    expect_command = True
    for token in tokens:
        if token in {"&&", "||", "|", ";"}:
            expect_command = True
            continue
        if token.startswith("-") or "=" in token and expect_command:
            continue
        if expect_command:
            commands.append(token.rsplit("/", 1)[-1])
            expect_command = False
    if commands:
        return commands

    first = command.split(maxsplit=1)[0]
    return [first.rsplit("/", 1)[-1]] if first else []


def _inspect_git(command: str) -> CommandSecurityResult:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return CommandSecurityResult(True, CommandRisk.UNKNOWN, "unable to parse git command", True)

    if len(tokens) < 2:
        return CommandSecurityResult(True, CommandRisk.READ_ONLY, "git help/status style command")

    subcommand = tokens[1]
    if subcommand in {"status", "log", "diff", "show", "branch", "rev-parse", "ls-files", "remote", "grep"}:
        return CommandSecurityResult(True, CommandRisk.READ_ONLY, f"git {subcommand} is read-only")
    if subcommand in {"fetch", "pull", "push", "clone"}:
        return CommandSecurityResult(True, CommandRisk.NETWORK, f"git {subcommand} uses network", True)
    return CommandSecurityResult(True, CommandRisk.WRITE, f"git {subcommand} mutates repository state", True)
