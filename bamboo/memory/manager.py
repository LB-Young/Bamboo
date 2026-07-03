"""Load editable memory knowledge into agent prompts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bamboo.factory.session import Session
from bamboo.memory.get_memory_path import get_memory_dir
from bamboo.memory.scope import MemoryScope

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
