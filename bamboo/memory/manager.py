"""Load editable memory knowledge into agent prompts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bamboo.factory.session import Session
from bamboo.memory.get_memory_path import get_memory_dir
from bamboo.memory.scope import MemoryScope
from bamboo.memory.source_log import search_source_logs

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
CHAT_TEMPLATE_NAMES = (
    "global.md",
    "profile.md",
    "preferences.md",
    "recurring_topics.md",
    "decisions.md",
    "open_questions.md",
)
PROJECT_TEMPLATE_NAMES = (
    "global.md",
    "overview.md",
    "architecture.md",
    "decisions.md",
    "coding_style.md",
    "bugs_and_fixes.md",
    "workflows.md",
    "open_questions.md",
)

KnowledgeUpdateOperation = Literal["append", "replace", "remove_matching"]


@dataclass(frozen=True, slots=True)
class MemoryKnowledgeFile:
    """One loaded editable knowledge file."""

    path: Path
    relative_path: str
    content: str


@dataclass(frozen=True, slots=True)
class MemoryPromptContext:
    """Knowledge context prepared for one agent prompt."""

    scope: MemoryScope
    knowledge_dir: Path
    knowledge_dirs: tuple[Path, ...]
    files: tuple[MemoryKnowledgeFile, ...]

    @property
    def content(self) -> str:
        """Render knowledge files into a prompt section body."""
        parts = []
        for file in self.files:
            parts.append(f"## {file.relative_path}\n\n{file.content}")
        return "\n\n".join(parts)


@dataclass(frozen=True, slots=True)
class MemoryUpdateResult:
    """Result of one memory knowledge file update."""

    scope: str
    file: str
    path: Path
    operation: str
    changed: bool
    source_refs: tuple[str, ...] = ()
    removed_count: int = 0

    @property
    def metadata(self) -> dict[str, object]:
        """Return JSON-serializable update metadata."""
        return {
            "scope": self.scope,
            "file": self.file,
            "path": str(self.path),
            "operation": self.operation,
            "changed": self.changed,
            "source_refs": list(self.source_refs),
            "removed_count": self.removed_count,
        }


class MemoryManager:
    """Manage editable chat/project knowledge files."""

    def __init__(self, *, memory_root: Path | None = None, template_dir: Path | None = None) -> None:
        self.memory_root = memory_root or get_memory_dir()
        self.template_dir = template_dir or TEMPLATE_DIR

    def load_prompt_context(self, session: Session) -> MemoryPromptContext:
        """Create missing templates and load non-empty knowledge for a session."""
        scope = self.resolve_scope(session)
        knowledge_dirs = self.knowledge_dirs_for_scope(scope)
        loaded_files: list[MemoryKnowledgeFile] = []
        for label, knowledge_dir in knowledge_dirs:
            if not self.ensure_knowledge_templates(scope, knowledge_dir):
                continue
            loaded_files.extend(self._load_knowledge_files(knowledge_dir, label=label, global_only=True))
        primary_dir = knowledge_dirs[-1][1]
        return MemoryPromptContext(
            scope=scope,
            knowledge_dir=primary_dir,
            knowledge_dirs=tuple(path for _, path in knowledge_dirs),
            files=tuple(loaded_files),
        )

    def resolve_scope(self, session: Session) -> MemoryScope:
        """Resolve memory scope from session context metadata."""
        prompt_mode = session.context.metadata.get("prompt_mode", "chat")
        if prompt_mode == "project":
            project_root = str(session.context.project_root)
            from bamboo.memory.get_memory_path import get_memory_dir_name

            project_hash = get_memory_dir_name(project_root)
            return MemoryScope(
                kind="project",
                root=self.memory_root / "projects",
                project_hash=project_hash,
                project_root=project_root,
            )
        return MemoryScope(kind="chat", root=self.memory_root / "dates")

    def knowledge_dir_for_scope(self, scope: MemoryScope) -> Path:
        """Return the primary editable knowledge directory for a scope."""
        return self.knowledge_dirs_for_scope(scope)[-1][1]

    def ensure_base_knowledge_templates(self) -> bool:
        """Create init-time chat and project-global knowledge templates."""
        chat_ok = self.ensure_knowledge_templates(
            MemoryScope(kind="chat", root=self.memory_root / "dates"),
            self.memory_root / "dates" / "chat" / "knowledge",
        )
        project_ok = self.ensure_knowledge_templates(
            MemoryScope(kind="project", root=self.memory_root / "projects"),
            self.memory_root / "projects" / "knowledge",
        )
        return chat_ok and project_ok

    def knowledge_dirs_for_scope(self, scope: MemoryScope) -> tuple[tuple[str, Path], ...]:
        """Return knowledge directories in prompt load order."""
        if scope.kind == "project":
            if not scope.project_hash:
                return (("project", scope.root / "knowledge"),)
            return (
                ("project-global", scope.root / "knowledge"),
                ("project-current", scope.root / scope.project_hash / "knowledge"),
            )
        return (("chat", scope.root / "chat" / "knowledge"),)

    def ensure_knowledge_templates(self, scope: MemoryScope, knowledge_dir: Path | None = None) -> bool:
        """Create missing knowledge files from package templates."""
        target_dir = knowledge_dir or self.knowledge_dir_for_scope(scope)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        template_names = CHAT_TEMPLATE_NAMES if scope.kind == "chat" else PROJECT_TEMPLATE_NAMES
        source_dir = self.template_dir / scope.kind
        for file_name in template_names:
            target_path = target_dir / file_name
            if target_path.exists():
                continue
            source_path = source_dir / file_name
            if source_path.is_file():
                content = source_path.read_text(encoding="utf-8")
            else:
                content = "<!-- Add stable knowledge here. Include source: session_id/task_id. -->\n"
            try:
                target_path.write_text(content, encoding="utf-8")
            except OSError:
                return False
        return True

    def load_knowledge_files_for_retrieval(self, session: Session) -> list[MemoryKnowledgeFile]:
        """Load all knowledge files for retrieval, including non-global files."""
        scope = self.resolve_scope(session)
        files: list[MemoryKnowledgeFile] = []
        for label, knowledge_dir in self.knowledge_dirs_for_scope(scope):
            if not self.ensure_knowledge_templates(scope, knowledge_dir):
                continue
            files.extend(self._load_knowledge_files(knowledge_dir, label=label, global_only=False))
        return files

    def allowed_scope_names(self, session: Session) -> set[str]:
        """Return editable memory scopes allowed for the current session."""
        scope = self.resolve_scope(session)
        if scope.kind == "project":
            return {"project-global", "project-current"}
        return {"chat"}

    def resolve_knowledge_scope_name(self, session: Session, scope_name: str = "auto") -> str:
        """Resolve tool scope name into a concrete editable scope."""
        normalized = scope_name or "auto"
        if normalized == "auto":
            return "project-current" if self.resolve_scope(session).kind == "project" else "chat"
        if normalized not in self.allowed_scope_names(session):
            raise ValueError(f"scope not allowed for current session: {normalized}")
        return normalized

    def knowledge_dir_for_name(self, session: Session, scope_name: str = "auto") -> Path:
        """Return the knowledge directory for a concrete tool scope."""
        resolved = self.resolve_knowledge_scope_name(session, scope_name)
        memory_scope = self.resolve_scope(session)
        if resolved == "chat":
            return self.memory_root / "dates" / "chat" / "knowledge"
        if resolved == "project-global":
            return self.memory_root / "projects" / "knowledge"
        if resolved == "project-current":
            if not memory_scope.project_hash:
                raise ValueError("current project scope is unavailable")
            return self.memory_root / "projects" / memory_scope.project_hash / "knowledge"
        raise ValueError(f"unsupported knowledge scope: {resolved}")

    def read_knowledge(self, session: Session, *, scope_name: str = "auto", file_name: str = "") -> list[MemoryKnowledgeFile]:
        """Safely read one or more knowledge files for the current session."""
        scope = self._scope_for_name(session, scope_name)
        directory = self.knowledge_dir_for_name(session, scope_name)
        if not self.ensure_knowledge_templates(scope, directory):
            raise ValueError("failed to ensure knowledge templates")
        if file_name:
            path = self._safe_knowledge_path(session, scope_name=scope_name, file_name=file_name)
            content = path.read_text(encoding="utf-8") if path.exists() else ""
            return [
                MemoryKnowledgeFile(
                    path=path,
                    relative_path=f"{self.resolve_knowledge_scope_name(session, scope_name)}/{path.name}",
                    content=content,
                )
            ]
        files: list[MemoryKnowledgeFile] = []
        label = self.resolve_knowledge_scope_name(session, scope_name)
        if not directory.is_dir():
            return files
        for path in sorted(directory.glob("*.md")):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            files.append(MemoryKnowledgeFile(path=path, relative_path=f"{label}/{path.name}", content=content))
        return files

    def update_knowledge(
        self,
        session: Session,
        *,
        scope_name: str = "auto",
        file_name: str,
        operation: KnowledgeUpdateOperation = "append",
        content: str = "",
        match_text: str = "",
        source_ref: str = "",
    ) -> MemoryUpdateResult:
        """Atomically update one editable knowledge markdown file."""
        if operation not in {"append", "replace", "remove_matching"}:
            raise ValueError(f"unsupported memory update operation: {operation}")
        path = self._safe_knowledge_path(session, scope_name=scope_name, file_name=file_name)
        scope = self._scope_for_name(session, scope_name)
        if not self.ensure_knowledge_templates(scope, path.parent):
            raise ValueError("failed to ensure knowledge templates")
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        changed = True
        removed_count = 0
        source_refs = tuple(ref for ref in [source_ref.strip()] if ref)
        if operation == "append":
            entry = self._prepare_knowledge_entry(content, source_ref=source_ref)
            separator = "" if existing.endswith("\n") or not existing else "\n"
            new_content = f"{existing}{separator}{entry}\n"
        elif operation == "replace":
            new_content = self._prepare_replace_content(content, source_ref=source_ref)
        else:
            if not match_text.strip():
                raise ValueError("match_text is required for remove_matching")
            lines = existing.splitlines()
            remaining = [line for line in lines if match_text not in line]
            removed_count = len(lines) - len(remaining)
            changed = removed_count > 0
            new_content = "\n".join(remaining).strip()
            if new_content:
                new_content += "\n"
        if changed:
            self._atomic_write(path, new_content)
        return MemoryUpdateResult(
            scope=self.resolve_knowledge_scope_name(session, scope_name),
            file=path.name,
            path=path,
            operation=operation,
            changed=changed,
            source_refs=source_refs,
            removed_count=removed_count,
        )

    def backfill_from_source_logs(
        self,
        session: Session,
        *,
        query: str,
        scope_name: str = "auto",
        file_name: str = "global.md",
        limit: int = 5,
    ) -> MemoryUpdateResult:
        """Append concise knowledge candidates from source log search results."""
        memory_scope = self.resolve_scope(session)
        matches = search_source_logs(query, memory_scope, limit=max(1, min(limit, 10)))
        if not matches:
            raise ValueError("no source log matches found")
        entries = []
        refs = []
        for match in matches:
            ref = f"{match.session_id}/{match.task_id}".strip("/")
            refs.append(ref)
            summary = self._summarize_source_log_content(match.content)
            if not summary:
                continue
            entries.append(f"- {summary} source: {ref}")
        if not entries:
            raise ValueError("no backfill candidates generated")
        result = self.update_knowledge(
            session,
            scope_name=scope_name,
            file_name=file_name,
            operation="append",
            content="\n".join(entries),
        )
        return MemoryUpdateResult(
            scope=result.scope,
            file=result.file,
            path=result.path,
            operation="backfill",
            changed=result.changed,
            source_refs=tuple(refs),
        )

    def _load_knowledge_files(
        self,
        knowledge_dir: Path,
        *,
        label: str,
        global_only: bool,
    ) -> list[MemoryKnowledgeFile]:
        files = []
        if not knowledge_dir.is_dir():
            return files
        for path in sorted(knowledge_dir.glob("*.md")):
            if global_only and path.name != "global.md":
                continue
            try:
                content = path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            content = self._strip_comment_only_template(content)
            if not content:
                continue
            files.append(
                MemoryKnowledgeFile(
                    path=path,
                    relative_path=f"{label}/{path.name}",
                    content=content,
                )
            )
        return files

    def _strip_comment_only_template(self, content: str) -> str:
        meaningful_lines = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("<!--") and stripped.endswith("-->"):
                continue
            if "Each entry should include `source:" in stripped:
                continue
            meaningful_lines.append(line)
        cleaned = "\n".join(meaningful_lines).strip()
        if "source:" not in cleaned:
            return ""
        return cleaned

    def _scope_for_name(self, session: Session, scope_name: str) -> MemoryScope:
        resolved = self.resolve_knowledge_scope_name(session, scope_name)
        if resolved == "chat":
            return MemoryScope(kind="chat", root=self.memory_root / "dates")
        memory_scope = self.resolve_scope(session)
        return MemoryScope(
            kind="project",
            root=self.memory_root / "projects",
            project_hash=memory_scope.project_hash if resolved == "project-current" else "",
            project_root=memory_scope.project_root,
        )

    def _safe_knowledge_path(self, session: Session, *, scope_name: str, file_name: str) -> Path:
        if not file_name or Path(file_name).is_absolute() or ".." in Path(file_name).parts or not file_name.endswith(".md"):
            raise ValueError("invalid knowledge file path")
        resolved = self.resolve_knowledge_scope_name(session, scope_name)
        allowed = CHAT_TEMPLATE_NAMES if resolved == "chat" else PROJECT_TEMPLATE_NAMES
        if file_name not in allowed:
            raise ValueError(f"knowledge file not allowed: {file_name}")
        directory = self.knowledge_dir_for_name(session, resolved)
        path = (directory / file_name).resolve(strict=False)
        directory_resolved = directory.resolve(strict=False)
        if directory_resolved not in path.parents and path != directory_resolved:
            raise ValueError("knowledge file escapes memory directory")
        return path

    def _prepare_knowledge_entry(self, content: str, *, source_ref: str = "") -> str:
        cleaned = content.strip()
        if not cleaned:
            raise ValueError("knowledge content is empty")
        if source_ref and "source:" not in cleaned:
            cleaned = f"{cleaned.rstrip()} source: {source_ref}"
        return cleaned

    def _prepare_replace_content(self, content: str, *, source_ref: str = "") -> str:
        cleaned = self._prepare_knowledge_entry(content, source_ref=source_ref)
        return cleaned if cleaned.endswith("\n") else f"{cleaned}\n"

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(path)

    def _summarize_source_log_content(self, content: str) -> str:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return ""
        summary = " ".join(lines)
        if len(summary) > 280:
            summary = summary[:277].rstrip() + "..."
        return summary.replace("\n", " ")
