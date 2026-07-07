"""Models for plugin manifest installation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PluginComponentType = Literal["skill", "command", "workflow", "mcp"]
PluginScanLevel = Literal["safe", "caution", "dangerous"]


@dataclass(frozen=True, slots=True)
class PluginComponent:
    """One installable component declared by a plugin manifest."""

    type: PluginComponentType
    path: str


@dataclass(frozen=True, slots=True)
class PluginMCPComponent:
    """MCP config declared by a plugin manifest."""

    path: str


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Validated bamboo-plugin.yaml contents."""

    name: str
    version: str
    description: str = ""
    publisher: str = ""
    skills: tuple[PluginComponent, ...] = ()
    commands: tuple[PluginComponent, ...] = ()
    workflows: tuple[PluginComponent, ...] = ()
    mcp: PluginMCPComponent | None = None
    permissions: tuple[str, ...] = ()
    compatibility: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PluginScanFinding:
    """One safety or validation finding for a plugin."""

    severity: PluginScanLevel | str
    category: str
    message: str
    path: str = ""
    line: int = 0


@dataclass(frozen=True, slots=True)
class PluginScanResult:
    """Complete plugin scan result."""

    level: PluginScanLevel | str
    ok: bool
    findings: tuple[PluginScanFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class PluginInstalledFile:
    """A target file installed by a plugin."""

    component_type: PluginComponentType | str
    source: str
    target: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PluginLockEntry:
    """Lockfile entry for one installed plugin."""

    schema_version: int
    name: str
    version: str
    description: str
    publisher: str
    source: str
    installed_at: str
    scan_level: str
    permissions: tuple[str, ...] = ()
    files: tuple[PluginInstalledFile, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PluginInstallResult:
    """Result of validating or installing a plugin."""

    name: str
    installed: bool
    reason: str
    scan_result: PluginScanResult
    lock_entry: PluginLockEntry | None = None


@dataclass(frozen=True, slots=True)
class PluginRemoveResult:
    """Result of removing an installed plugin."""

    name: str
    removed: bool
    deleted_files: tuple[str, ...] = ()
    kept_files: tuple[str, ...] = ()
    reason: str = ""
