"""Install plugin manifest packages into Bamboo userspace."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from bamboo.plugins.manifest import load_plugin_manifest
from bamboo.plugins.models import (
    PluginInstallResult,
    PluginInstalledFile,
    PluginLockEntry,
    PluginManifest,
    PluginRemoveResult,
    PluginScanFinding,
    PluginScanResult,
)
from bamboo.security import inspect_command
from bamboo.skills.guard import PATTERNS, MAX_SCAN_BYTES
from bamboo.skills.store import utc_now
from bamboo.userspace.userspace import get_userspace_dir


class PluginInstaller:
    """Validates, installs and removes local plugin packages."""

    def __init__(self, *, userspace_dir: Path | None = None) -> None:
        self.userspace_dir = userspace_dir or get_userspace_dir()

    def validate(self, plugin_dir: Path) -> PluginInstallResult:
        """Validate and scan a plugin directory without installing it."""
        source = plugin_dir.expanduser().resolve()
        manifest = load_plugin_manifest(source)
        scan = scan_plugin(source, manifest)
        return PluginInstallResult(name=manifest.name, installed=False, reason="validated", scan_result=scan)

    def install(
        self,
        plugin_dir: Path,
        *,
        force: bool = False,
        overwrite: bool = False,
    ) -> PluginInstallResult:
        """Install a local plugin package after quarantine and scan."""
        source = plugin_dir.expanduser().resolve()
        manifest = load_plugin_manifest(source)
        quarantine_path = self._quarantine_path(manifest)
        if quarantine_path.exists():
            shutil.rmtree(quarantine_path)
        quarantine_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, quarantine_path)

        quarantined_manifest = load_plugin_manifest(quarantine_path)
        scan = scan_plugin(quarantine_path, quarantined_manifest)
        if scan.level == "dangerous" and not force:
            self._audit("install-blocked", quarantined_manifest, "dangerous scan findings", scan)
            return PluginInstallResult(
                name=quarantined_manifest.name,
                installed=False,
                reason="dangerous scan findings",
                scan_result=scan,
            )

        targets = self._planned_targets(quarantine_path, quarantined_manifest)
        conflict = _first_existing_target(targets)
        if conflict is not None and not overwrite:
            reason = f"target already exists: {conflict}"
            self._audit("install-blocked", quarantined_manifest, reason, scan)
            return PluginInstallResult(quarantined_manifest.name, False, reason, scan)

        installed_files: list[PluginInstalledFile] = []
        for component_type, source_path, target_path in targets:
            if target_path.exists():
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if source_path.is_dir():
                shutil.copytree(source_path, target_path)
                for file_path in sorted(target_path.rglob("*")):
                    if file_path.is_file():
                        installed_files.append(
                            PluginInstalledFile(
                                component_type=component_type,
                                source=str(source_path.relative_to(quarantine_path)),
                                target=str(file_path),
                                sha256=sha256_file(file_path),
                            )
                        )
            else:
                shutil.copy2(source_path, target_path)
                installed_files.append(
                    PluginInstalledFile(
                        component_type=component_type,
                        source=str(source_path.relative_to(quarantine_path)),
                        target=str(target_path),
                        sha256=sha256_file(target_path),
                    )
                )

        entry = PluginLockEntry(
            schema_version=1,
            name=quarantined_manifest.name,
            version=quarantined_manifest.version,
            description=quarantined_manifest.description,
            publisher=quarantined_manifest.publisher,
            source=str(source),
            installed_at=utc_now(),
            scan_level=str(scan.level),
            permissions=quarantined_manifest.permissions,
            files=tuple(installed_files),
            metadata={"quarantine_path": str(quarantine_path)},
        )
        lock = self.load_lock()
        lock[entry.name] = entry
        self.save_lock(lock)
        self._audit("install", quarantined_manifest, "installed", scan, entry)
        return PluginInstallResult(entry.name, True, "installed", scan, entry)

    def list(self) -> list[PluginLockEntry]:
        """Return installed plugin lock entries."""
        return sorted(self.load_lock().values(), key=lambda item: item.name)

    def show(self, name: str) -> PluginLockEntry | None:
        """Return one installed plugin lock entry."""
        return self.load_lock().get(name)

    def remove(self, name: str, *, force: bool = False) -> PluginRemoveResult:
        """Remove files installed by a plugin, preserving user-modified files by default."""
        lock = self.load_lock()
        entry = lock.get(name)
        if entry is None:
            return PluginRemoveResult(name=name, removed=False, reason=f"plugin not installed: {name}")
        deleted: list[str] = []
        kept: list[str] = []
        for installed_file in sorted(entry.files, key=lambda item: item.target, reverse=True):
            target = Path(installed_file.target)
            if not target.exists():
                continue
            changed = target.is_file() and sha256_file(target) != installed_file.sha256
            if changed and not force:
                kept.append(str(target))
                continue
            if target.is_file():
                target.unlink()
                deleted.append(str(target))
                _remove_empty_parents(target.parent, stop_at=self.userspace_dir)
        if kept:
            self._audit("remove-partial", entry, f"kept {len(kept)} modified file(s)")
            return PluginRemoveResult(name=name, removed=False, deleted_files=tuple(deleted), kept_files=tuple(kept), reason="modified files kept")
        lock.pop(name, None)
        self.save_lock(lock)
        self._audit("remove", entry, "removed")
        return PluginRemoveResult(name=name, removed=True, deleted_files=tuple(deleted), reason="removed")

    def load_lock(self) -> dict[str, PluginLockEntry]:
        """Read installed plugin lockfile."""
        path = self.lock_path()
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        raw_entries = data.get("plugins", data)
        if not isinstance(raw_entries, dict):
            return {}
        entries: dict[str, PluginLockEntry] = {}
        for name, raw_entry in raw_entries.items():
            if not isinstance(raw_entry, dict):
                continue
            raw_files = raw_entry.get("files", [])
            if not isinstance(raw_files, list):
                raw_files = []
            try:
                files = tuple(PluginInstalledFile(**item) for item in raw_files if isinstance(item, dict))
                entry = PluginLockEntry(
                    schema_version=int(raw_entry.get("schema_version", 1)),
                    name=str(raw_entry.get("name") or name),
                    version=str(raw_entry.get("version") or ""),
                    description=str(raw_entry.get("description") or ""),
                    publisher=str(raw_entry.get("publisher") or ""),
                    source=str(raw_entry.get("source") or ""),
                    installed_at=str(raw_entry.get("installed_at") or ""),
                    scan_level=str(raw_entry.get("scan_level") or "unknown"),
                    permissions=tuple(raw_entry.get("permissions") or ()),
                    files=files,
                    metadata=dict(raw_entry.get("metadata") or {}),
                )
            except (TypeError, ValueError):
                continue
            entries[entry.name] = entry
        return entries

    def save_lock(self, entries: dict[str, PluginLockEntry]) -> None:
        """Write installed plugin lockfile."""
        payload = {"schema_version": 1, "plugins": {name: asdict(entry) for name, entry in sorted(entries.items())}}
        path = self.lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def lock_path(self) -> Path:
        """Return plugin lockfile path."""
        return self.userspace_dir / "storage" / "plugins" / "lock.json"

    def audit_path(self) -> Path:
        """Return plugin audit JSONL path."""
        return self.userspace_dir / "storage" / "plugins" / "audit.jsonl"

    def _quarantine_path(self, manifest: PluginManifest) -> Path:
        digest = hashlib.sha256(f"{manifest.name}:{manifest.version}".encode("utf-8")).hexdigest()[:12]
        return self.userspace_dir / "plugins" / "quarantine" / f"{manifest.name}-{manifest.version}-{digest}"

    def _planned_targets(self, plugin_root: Path, manifest: PluginManifest) -> list[tuple[str, Path, Path]]:
        targets: list[tuple[str, Path, Path]] = []
        for component in manifest.skills:
            source = (plugin_root / component.path).resolve()
            _require_dir(source, "skill")
            if not (source / "SKILL.md").is_file():
                raise ValueError(f"skill component missing SKILL.md: {component.path}")
            targets.append(("skill", source, self.userspace_dir / "skills" / source.name))
        for component in manifest.commands:
            source = (plugin_root / component.path).resolve()
            _require_file(source, "command")
            if source.suffix != ".md":
                raise ValueError(f"command component must be a markdown file: {component.path}")
            targets.append(("command", source, self.userspace_dir / "commands" / source.name))
        for component in manifest.workflows:
            source = (plugin_root / component.path).resolve()
            _require_dir(source, "workflow")
            if not (source / "WORKFLOW.md").is_file():
                raise ValueError(f"workflow component missing WORKFLOW.md: {component.path}")
            targets.append(("workflow", source, self.userspace_dir / "workflows" / source.name))
        if manifest.mcp is not None:
            source = (plugin_root / manifest.mcp.path).resolve()
            _require_file(source, "mcp")
            targets.append(("mcp", source, self.userspace_dir / "configs" / "mcp.d" / f"{manifest.name}.yaml"))
        _reject_duplicate_targets(targets)
        return targets

    def _audit(
        self,
        action: str,
        plugin: PluginManifest | PluginLockEntry,
        reason: str,
        scan: PluginScanResult | None = None,
        entry: PluginLockEntry | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "ts": utc_now(),
            "action": action,
            "plugin_name": plugin.name,
            "version": plugin.version,
            "reason": reason,
        }
        if scan is not None:
            payload["scan_level"] = scan.level
            payload["findings"] = [asdict(finding) for finding in scan.findings]
        if entry is not None:
            payload["files"] = [asdict(file) for file in entry.files]
        path = self.audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def scan_plugin(plugin_root: Path, manifest: PluginManifest | None = None) -> PluginScanResult:
    """Scan plugin files and MCP server declarations for risky content."""
    root = plugin_root.resolve()
    manifest = manifest or load_plugin_manifest(root)
    findings: list[PluginScanFinding] = []
    for file_path in _iter_scan_files(root):
        relative = str(file_path.relative_to(root))
        content = _read_text_limited(file_path)
        if content is None:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for severity, category, pattern, message in PATTERNS:
                if pattern.search(line):
                    findings.append(PluginScanFinding(severity=severity, category=category, message=message, path=relative, line=line_number))
    if manifest.mcp is not None:
        findings.extend(_scan_mcp_config(root / manifest.mcp.path, manifest.mcp.path))
    level = "safe"
    if any(finding.severity == "dangerous" for finding in findings):
        level = "dangerous"
    elif findings:
        level = "caution"
    return PluginScanResult(level=level, ok=level != "dangerous", findings=tuple(findings))


def sha256_file(path: Path) -> str:
    """Return sha256 for one file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_mcp_config(path: Path, relative_path: str) -> list[PluginScanFinding]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [PluginScanFinding("dangerous", "invalid-mcp", f"unable to parse MCP config: {exc}", relative_path)]
    raw_mcp = data.get("mcp", data) if isinstance(data, dict) else {}
    servers = raw_mcp.get("servers", {}) if isinstance(raw_mcp, dict) else {}
    if not servers:
        return []
    iterable = servers.items() if isinstance(servers, dict) else enumerate(servers) if isinstance(servers, list) else []
    findings: list[PluginScanFinding] = []
    for server_name, raw_server in iterable:
        if not isinstance(raw_server, dict):
            continue
        command = raw_server.get("command")
        if not isinstance(command, str) or not command.strip():
            continue
        result = inspect_command(command)
        if not result.allowed or result.risk.value != "read_only":
            severity = "dangerous" if not result.allowed or result.risk.value == "destructive" else "caution"
            findings.append(
                PluginScanFinding(
                    severity,
                    "mcp-command-risk",
                    f"MCP server {server_name} command risk={result.risk.value}: {result.reason}",
                    relative_path,
                )
            )
    return findings


def _iter_scan_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.parts and path.stat().st_size <= MAX_SCAN_BYTES
    ]


def _read_text_limited(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    return raw[:MAX_SCAN_BYTES].decode("utf-8", errors="ignore")


def _first_existing_target(targets: list[tuple[str, Path, Path]]) -> Path | None:
    for _, _, target in targets:
        if target.exists():
            return target
    return None


def _reject_duplicate_targets(targets: list[tuple[str, Path, Path]]) -> None:
    seen: set[Path] = set()
    for _, _, target in targets:
        if target in seen:
            raise ValueError(f"duplicate plugin target path: {target}")
        seen.add(target)


def _require_dir(path: Path, label: str) -> None:
    if not path.is_dir():
        raise FileNotFoundError(f"{label} component directory not found: {path}")


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} component file not found: {path}")


def _remove_empty_parents(path: Path, *, stop_at: Path) -> None:
    stop = stop_at.resolve()
    current = path.resolve()
    while current != stop and current.is_relative_to(stop):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
