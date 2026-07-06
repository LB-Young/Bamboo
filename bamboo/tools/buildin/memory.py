"""Built-in memory maintenance tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from bamboo.factory.task_factory import Task
from bamboo.memory.manager import MemoryManager
from bamboo.memory.retrieval import retrieve_memory
from bamboo.tools.buildin.base import Tool, ToolResult

if TYPE_CHECKING:
    from bamboo.runtime.runtime_context import RuntimeContext

MemoryScopeArg = Literal["auto", "chat", "project-global", "project-current"]
MemoryUpdateOperationArg = Literal["append", "replace", "remove_matching"]


class _MemoryTool(Tool):
    """Base class for tools that need current runtime memory scope."""

    tags = ("memory",)

    def __init__(self, *, memory_manager: MemoryManager | None = None) -> None:
        self.memory_manager = memory_manager
        self.runtime_context: RuntimeContext | None = None
        self.task: Task | None = None

    def bind_runtime_context(self, *, runtime_context: RuntimeContext, task: Task) -> None:
        """Bind current runtime context before execution."""
        self.runtime_context = runtime_context
        self.task = task

    def _manager_and_task(self) -> tuple[MemoryManager, Task] | ToolResult:
        if self.runtime_context is None or self.task is None:
            return ToolResult(
                content=f"{self.name} is unavailable outside AgentRuntime",
                success=False,
                error="missing_runtime_context",
            )
        manager = self.memory_manager or self.runtime_context.memory_manager
        if not isinstance(manager, MemoryManager):
            return ToolResult(content="No memory manager is configured", success=False, error="missing_memory_manager")
        return manager, self.task


class MemoryReadTool(_MemoryTool):
    """Read editable memory knowledge files in the current session scope."""

    name = "memory_read"
    description = "Read editable Bamboo memory knowledge files for the current chat/project scope."
    risk_level = "read"
    tags = ("memory", "read")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["auto", "chat", "project-global", "project-current"],
                    "description": "Memory scope. auto resolves to chat or current project.",
                },
                "file": {"type": "string", "description": "Optional knowledge md file name, e.g. global.md."},
            },
        }

    async def execute(self, scope: MemoryScopeArg = "auto", file: str = "") -> ToolResult:
        resolved = self._manager_and_task()
        if isinstance(resolved, ToolResult):
            return resolved
        manager, task = resolved
        try:
            files = manager.read_knowledge(task.session, scope_name=scope, file_name=file)
        except Exception as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        if not files:
            return ToolResult(
                content=f'<memory_files scope="{scope}" count="0" />',
                metadata={"scope": scope, "files": []},
            )
        parts = [f'<memory_files scope="{scope}" count="{len(files)}">']
        metadata_files = []
        for item in files:
            parts.append(f'<file path="{item.relative_path}">\n{item.content}\n</file>')
            metadata_files.append({"path": str(item.path), "relative_path": item.relative_path})
        parts.append("</memory_files>")
        return ToolResult(content="\n".join(parts), metadata={"scope": scope, "files": metadata_files})


class MemorySearchTool(_MemoryTool):
    """Search editable memory knowledge files in the current session scope."""

    name = "memory_search"
    description = "Search editable Bamboo memory knowledge files in the current chat/project scope."
    risk_level = "read"
    tags = ("memory", "read", "search")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "limit": {"type": "integer", "description": "Maximum number of results, 1-20."},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, limit: int = 5) -> ToolResult:
        resolved = self._manager_and_task()
        if isinstance(resolved, ToolResult):
            return resolved
        manager, task = resolved
        matches = retrieve_memory(
            query=query,
            session=task.session,
            memory_manager=manager,
            source="knowledge",
            limit=limit,
        )
        if not matches:
            return ToolResult(
                content=f'<memory_search query="{query}" count="0" />',
                metadata={"query": query, "matches": []},
            )
        parts = [f'<memory_search query="{query}" count="{len(matches)}">']
        metadata_matches = []
        for index, match in enumerate(matches, start=1):
            parts.append(
                f'<result index="{index}" score="{match.score}" source="{match.source}">\n'
                f"{match.content}\n"
                "</result>"
            )
            metadata_matches.append({"source": match.source, "score": match.score})
        parts.append("</memory_search>")
        return ToolResult(content="\n".join(parts), metadata={"query": query, "matches": metadata_matches})


class MemoryUpdateTool(_MemoryTool):
    """Update editable memory knowledge files in the current session scope."""

    name = "memory_update"
    description = (
        "Update editable Bamboo memory knowledge. Use append to remember, replace to rewrite one file, "
        "or remove_matching to forget matching lines."
    )
    risk_level = "write"
    tags = ("memory", "write")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["auto", "chat", "project-global", "project-current"],
                    "description": "Memory scope. auto resolves to chat or current project.",
                },
                "file": {"type": "string", "description": "Knowledge md file name."},
                "operation": {
                    "type": "string",
                    "enum": ["append", "replace", "remove_matching"],
                    "description": "Update operation.",
                },
                "content": {"type": "string", "description": "Content for append or replace."},
                "match_text": {"type": "string", "description": "Substring to remove for remove_matching."},
                "source_ref": {
                    "type": "string",
                    "description": "Optional source ref like session_id/task_id; appended when content lacks source:.",
                },
            },
            "required": ["file", "operation"],
        }

    async def execute(
        self,
        file: str,
        operation: MemoryUpdateOperationArg,
        scope: MemoryScopeArg = "auto",
        content: str = "",
        match_text: str = "",
        source_ref: str = "",
    ) -> ToolResult:
        resolved = self._manager_and_task()
        if isinstance(resolved, ToolResult):
            return resolved
        manager, task = resolved
        try:
            result = manager.update_knowledge(
                task.session,
                scope_name=scope,
                file_name=file,
                operation=operation,
                content=content,
                match_text=match_text,
                source_ref=source_ref,
            )
        except Exception as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        return ToolResult(
            content=(
                f"memory_update {result.operation} {result.scope}/{result.file} "
                f"changed={result.changed} removed={result.removed_count}"
            ),
            metadata=result.metadata,
        )


class MemoryBackfillTool(_MemoryTool):
    """Backfill concise knowledge entries from source logs."""

    name = "memory_backfill"
    description = "Search source logs and append concise, sourced knowledge entries to editable memory."
    risk_level = "write"
    tags = ("memory", "write", "backfill")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Source log search query."},
                "scope": {
                    "type": "string",
                    "enum": ["auto", "chat", "project-global", "project-current"],
                    "description": "Memory scope. auto resolves to chat or current project.",
                },
                "file": {"type": "string", "description": "Knowledge md file name."},
                "limit": {"type": "integer", "description": "Maximum source log matches, 1-10."},
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        scope: MemoryScopeArg = "auto",
        file: str = "global.md",
        limit: int = 5,
    ) -> ToolResult:
        resolved = self._manager_and_task()
        if isinstance(resolved, ToolResult):
            return resolved
        manager, task = resolved
        try:
            result = manager.backfill_from_source_logs(
                task.session,
                query=query,
                scope_name=scope,
                file_name=file,
                limit=limit,
            )
        except Exception as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        return ToolResult(
            content=(
                f"memory_backfill appended {len(result.source_refs)} source refs "
                f"to {result.scope}/{result.file}"
            ),
            metadata=result.metadata,
        )
