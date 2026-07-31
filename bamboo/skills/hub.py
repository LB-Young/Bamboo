"""External skill installation through quarantine, scan, lockfile, and audit."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from bamboo.skills.creator import load_skill_definition
from bamboo.skills.guard import scan_skill, scan_skill_for_install, should_allow_install
from bamboo.skills.models import SkillHubLockEntry, SkillScanResult
from bamboo.skills.store import SkillStore, utc_now
from bamboo.skills.validator import SkillValidator
from bamboo.userspace.userspace import get_user_skills_dir


@dataclass(frozen=True, slots=True)
class SkillBundle:
    """A fetched skill bundle in quarantine."""

    identifier: str
    path: Path
    source: str
    source_type: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class SkillInstallResult:
    """Result of installing or blocking a skill bundle."""

    name: str
    installed: bool
    destination: Path | None
    scan_result: SkillScanResult
    reason: str
    lock_entry: SkillHubLockEntry | None = None


class SkillSource:
    """Fetches an external skill into a destination directory."""

    source_type = "unknown"

    def fetch(self, identifier: str, destination: Path) -> SkillBundle:
        """Fetch an identifier into destination."""
        raise NotImplementedError


class LocalSkillSource(SkillSource):
    """Copies a local skill directory into quarantine."""

    source_type = "local"

    def fetch(self, identifier: str, destination: Path) -> SkillBundle:
        source_path = _local_identifier_path(identifier)
        if not source_path.is_dir():
            raise FileNotFoundError(f"Skill source directory not found: {source_path}")
        if not (source_path / "SKILL.md").is_file():
            raise FileNotFoundError(f"Skill source is missing SKILL.md: {source_path}")
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source_path, destination)
        return SkillBundle(
            identifier=identifier,
            path=destination,
            source=str(source_path),
            source_type=self.source_type,
            content_hash=hash_directory(destination),
        )


class GitHubSkillSource(SkillSource):
    """Placeholder for GitHub skill source.

    Network fetching is intentionally not implemented in Phase 5 tests. The
    class exists so callers can inject a real implementation later without
    changing SkillHub's install flow.
    """

    source_type = "github"

    def fetch(self, identifier: str, destination: Path) -> SkillBundle:
        raise RuntimeError("GitHub skill fetch is not implemented; use an injected SkillSource")


class SkillHub:
    """Installs external skills safely."""

    def __init__(
        self,
        *,
        store: SkillStore | None = None,
        skills_dir: Path | None = None,
        sources: dict[str, SkillSource] | None = None,
        validator: SkillValidator | None = None,
        install_scanner: Callable[[Path, str], SkillScanResult] | None = None,
    ) -> None:
        self.store = store or SkillStore()
        self.skills_dir = skills_dir or get_user_skills_dir()
        self.sources = sources or {"local": LocalSkillSource(), "github": GitHubSkillSource()}
        self.validator = validator or SkillValidator()
        self.install_scanner = install_scanner or scan_skill_for_install

    def install(
        self,
        identifier: str,
        *,
        trust_level: str = "community",
        force: bool = False,
        overwrite: bool = False,
    ) -> SkillInstallResult:
        """Install a skill from an external source."""
        source_type = _source_type(identifier)
        source = self.sources.get(source_type)
        if source is None:
            raise ValueError(f"Unsupported skill source: {source_type}")

        quarantine_root = self.store.quarantine_dir()
        quarantine_root.mkdir(parents=True, exist_ok=True)
        quarantine_path = quarantine_root / _safe_quarantine_name(identifier)
        bundle = source.fetch(identifier, quarantine_path)
        definition = load_skill_definition(bundle.path, source=source_type)
        validation = self.validator.validate(definition)
        if not validation.ok:
            scan_result = scan_skill(bundle.path, source=bundle.source)
            reason = f"skill validation failed: {validation.errors}"
            self._audit("install-blocked", definition.name or bundle.path.name, identifier, reason, scan_result)
            return SkillInstallResult(definition.name or bundle.path.name, False, None, scan_result, reason)

        scan_result = self.install_scanner(bundle.path, bundle.source)
        allowed, reason = should_allow_install(scan_result, trust_level, force=force)
        if not allowed:
            self._audit("install-blocked", definition.name, identifier, reason, scan_result)
            return SkillInstallResult(definition.name, False, None, scan_result, reason)

        destination = self.skills_dir / definition.name
        if destination.exists():
            if not overwrite:
                reason = f"skill already exists: {destination}"
                self._audit("install-blocked", definition.name, identifier, reason, scan_result)
                return SkillInstallResult(definition.name, False, destination, scan_result, reason)
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle.path, destination)

        entry = SkillHubLockEntry(
            schema_version=1,
            name=definition.name,
            source=bundle.source,
            source_type=bundle.source_type,
            trust_level=trust_level,
            installed_at=utc_now(),
            source_path=str(destination),
            content_hash=bundle.content_hash,
            scan_level=scan_result.level,
            blocked=False,
            metadata={"identifier": identifier},
        )
        lock = self.store.load_hub_lock()
        lock[definition.name] = entry
        self.store.save_hub_lock(lock)
        self._audit("install", definition.name, identifier, reason, scan_result)
        return SkillInstallResult(definition.name, True, destination, scan_result, reason, entry)

    def _audit(
        self,
        action: str,
        name: str,
        identifier: str,
        reason: str,
        scan_result: SkillScanResult,
    ) -> None:
        self.store.append_hub_audit(
            {
                "action": action,
                "skill_name": name,
                "identifier": identifier,
                "reason": reason,
                "scan_level": scan_result.level,
                "findings": [asdict(finding) for finding in scan_result.findings],
            }
        )


def hash_directory(path: Path) -> str:
    """Return a stable sha256 for a directory tree."""
    digest = hashlib.sha256()
    for file_path in sorted(path.rglob("*")):
        if not file_path.is_file():
            continue
        digest.update(str(file_path.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _source_type(identifier: str) -> str:
    if identifier.startswith("github:"):
        return "github"
    if identifier.startswith("local:") or identifier.startswith("path:"):
        return "local"
    parsed = urlparse(identifier)
    if parsed.scheme in {"", "file"}:
        return "local"
    return parsed.scheme


def _local_identifier_path(identifier: str) -> Path:
    if identifier.startswith("local:"):
        return Path(identifier.removeprefix("local:")).expanduser().resolve()
    if identifier.startswith("path:"):
        return Path(identifier.removeprefix("path:")).expanduser().resolve()
    if identifier.startswith("file://"):
        return Path(urlparse(identifier).path).expanduser().resolve()
    return Path(identifier).expanduser().resolve()


def _safe_quarantine_name(identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:12]
    label = "".join(char if char.isalnum() else "-" for char in identifier)[-40:].strip("-")
    return f"{label or 'skill'}-{digest}"
