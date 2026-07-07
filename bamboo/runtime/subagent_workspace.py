"""Workspace isolation helpers for writable subagents."""

from __future__ import annotations

import difflib
import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from bamboo.subagents.models import SubagentDefinition, WorkspaceMode
from bamboo.tools.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class WorkspaceDiff:
    """Summary of files changed inside an isolated workspace."""

    changed_files: tuple[str, ...] = ()
    diff_stat: str = ""
    diff_patch_path: str = ""

    @property
    def has_changes(self) -> bool:
        return bool(self.changed_files)


@dataclass(slots=True)
class SubagentWorkspace:
    """Resolved workspace for one subagent run."""

    requested_mode: WorkspaceMode
    mode: WorkspaceMode
    original_project: Path
    path: Path
    retained: bool = False
    note: str = ""
    _snapshot: dict[str, str] = field(default_factory=dict)

    @property
    def isolated(self) -> bool:
        return self.mode in {"tempdir", "worktree"}


class SubagentWorkspaceManager:
    """Create, diff, and clean up subagent workspaces."""

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or Path(tempfile.gettempdir()) / "bamboo-subagents"

    def prepare(
        self,
        *,
        definition: SubagentDefinition,
        project_root: Path,
        tool_registry: ToolRegistry,
    ) -> SubagentWorkspace:
        """Prepare an appropriate workspace for a subagent definition."""
        project = project_root.expanduser().resolve(strict=False)
        requested_mode = self._effective_mode(definition, tool_registry)
        if requested_mode in {"shared", "read_only"}:
            return SubagentWorkspace(
                requested_mode=requested_mode,
                mode=requested_mode,
                original_project=project,
                path=project,
            )
        if requested_mode == "worktree":
            worktree = self._try_create_worktree(definition, project)
            if worktree is not None:
                return worktree
            workspace = self._create_tempdir(definition, project)
            workspace.requested_mode = "worktree"
            workspace.note = "worktree unavailable; fell back to tempdir"
            return workspace
        return self._create_tempdir(definition, project)

    def collect_diff(self, workspace: SubagentWorkspace) -> WorkspaceDiff:
        """Collect changed files and diff stat for an isolated workspace."""
        if workspace.mode == "worktree":
            return self._collect_git_diff(workspace)
        if workspace.mode == "tempdir":
            return self._collect_tempdir_diff(workspace)
        return WorkspaceDiff()

    def finalize(self, workspace: SubagentWorkspace, diff: WorkspaceDiff, *, success: bool, keep_on_success: bool) -> None:
        """Clean or retain an isolated workspace based on outcome and changes."""
        if not workspace.isolated:
            workspace.retained = False
            return
        should_retain = (not success) or diff.has_changes or keep_on_success
        workspace.retained = should_retain
        if should_retain:
            return
        shutil.rmtree(workspace.path, ignore_errors=True)

    def _effective_mode(self, definition: SubagentDefinition, tool_registry: ToolRegistry) -> WorkspaceMode:
        if definition.workspace_mode != "shared":
            return definition.workspace_mode
        if self._needs_isolation(definition, tool_registry):
            return "tempdir"
        return "shared"

    def _needs_isolation(self, definition: SubagentDefinition, tool_registry: ToolRegistry) -> bool:
        for name, mode in definition.tools.items():
            if not mode or mode == "read_only":
                continue
            metadata = tool_registry.get_metadata(name)
            risk = metadata.risk_level if metadata is not None else "unknown"
            if risk in {"write", "execute", "network", "unknown"}:
                return True
        return False

    def _create_tempdir(self, definition: SubagentDefinition, project: Path) -> SubagentWorkspace:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{definition.name}-{uuid4().hex[:8]}"
        ignore = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".ruff_cache", "*.pyc", ".DS_Store")
        if project.is_dir():
            shutil.copytree(project, target, ignore=ignore)
        else:
            target.mkdir(parents=True, exist_ok=True)
        workspace = SubagentWorkspace(
            requested_mode="tempdir",
            mode="tempdir",
            original_project=project,
            path=target,
        )
        workspace._snapshot = _snapshot_files(target)
        return workspace

    def _try_create_worktree(self, definition: SubagentDefinition, project: Path) -> SubagentWorkspace | None:
        if not _is_git_repo(project):
            return None
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{definition.name}-{uuid4().hex[:8]}"
        result = subprocess.run(
            ["git", "-C", str(project), "worktree", "add", "--detach", str(target), "HEAD"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return SubagentWorkspace(
            requested_mode="worktree",
            mode="worktree",
            original_project=project,
            path=target,
        )

    def _collect_git_diff(self, workspace: SubagentWorkspace) -> WorkspaceDiff:
        status = subprocess.run(
            ["git", "-C", str(workspace.path), "status", "--porcelain"],
            text=True,
            capture_output=True,
            check=False,
        )
        changed = tuple(
            sorted(
                line[3:].strip()
                for line in status.stdout.splitlines()
                if len(line) > 3 and line[3:].strip()
            )
        )
        stat = subprocess.run(
            ["git", "-C", str(workspace.path), "diff", "--stat"],
            text=True,
            capture_output=True,
            check=False,
        )
        patch_path = ""
        if changed:
            patch = subprocess.run(
                ["git", "-C", str(workspace.path), "diff", "--binary"],
                text=True,
                capture_output=True,
                check=False,
            )
            patch_path = _write_patch(workspace.path, patch.stdout)
        return WorkspaceDiff(changed_files=changed, diff_stat=stat.stdout.strip(), diff_patch_path=patch_path)

    def _collect_tempdir_diff(self, workspace: SubagentWorkspace) -> WorkspaceDiff:
        current = _snapshot_files(workspace.path)
        changed = tuple(sorted(path for path in set(workspace._snapshot) | set(current) if workspace._snapshot.get(path) != current.get(path)))
        if not changed:
            return WorkspaceDiff()
        patch_parts = []
        added = removed = 0
        for relative_path in changed:
            before = _read_text_if_possible(workspace.original_project / relative_path, missing_hash=workspace._snapshot.get(relative_path, ""))
            after = _read_text_if_possible(workspace.path / relative_path, missing_hash=current.get(relative_path, ""))
            if before is None or after is None:
                patch_parts.append(f"Binary or unreadable change: {relative_path}\n")
                continue
            before_lines = before.splitlines(keepends=True)
            after_lines = after.splitlines(keepends=True)
            added += max(0, len(after_lines) - len(before_lines))
            removed += max(0, len(before_lines) - len(after_lines))
            patch_parts.extend(
                difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=f"a/{relative_path}",
                    tofile=f"b/{relative_path}",
                )
            )
        stat = f"{len(changed)} files changed"
        if added or removed:
            stat = f"{stat}, +{added} -{removed}"
        return WorkspaceDiff(
            changed_files=changed,
            diff_stat=stat,
            diff_patch_path=_write_patch(workspace.path, "".join(patch_parts)),
        )


def _is_git_repo(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _snapshot_files(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    if not root.is_dir():
        return snapshot
    for path in root.rglob("*"):
        if not path.is_file() or _ignored_path(path):
            continue
        relative = path.relative_to(root).as_posix()
        snapshot[relative] = _file_hash(path)
    return snapshot


def _ignored_path(path: Path) -> bool:
    return any(part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"} for part in path.parts)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _read_text_if_possible(path: Path, *, missing_hash: str) -> str | None:
    if not missing_hash:
        return ""
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _write_patch(workspace: Path, content: str) -> str:
    patch_path = workspace / ".bamboo-subagent.diff"
    patch_path.write_text(content, encoding="utf-8")
    return str(patch_path)
