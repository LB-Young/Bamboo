"""Sandbox configuration placeholders for future isolated execution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    """Describes execution limits for a future sandbox runner."""

    enabled: bool = False
    writable_roots: tuple[str, ...] = ()
    env_allowlist: tuple[str, ...] = ("PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR")
    network_enabled: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Result returned by sandbox policy checks."""

    allowed: bool
    reason: str = ""
