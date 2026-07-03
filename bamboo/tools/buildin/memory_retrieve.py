"""Built-in memory retrieval tool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from bamboo.factory.task_factory import Task
from bamboo.memory.manager import MemoryManager
from bamboo.memory.retrieval import retrieve_memory
from bamboo.tools.buildin.base import Tool, ToolResult

if TYPE_CHECKING:
    from bamboo.runtime.runtime_context import RuntimeContext

MemorySource = Literal["knowledge", "source_log", "all"]


class MemoryRetrieveTool(Tool):
    """Retrieve editable knowledge or raw source logs on demand."""

    name = "memory_retrieve"
    description = (
        "Retrieve Bamboo memory on demand. Use source='knowledge' for editable md knowledge, "
        "source='source_log' for raw turns/messages jsonl evidence, or source='all' for both."
    )
    risk_level = "read"
    tags = ("memory", "read", "retrieval")

    def __init__(self, *, memory_manager: MemoryManager | None = None) -> None:
        self.memory_manager = memory_manager
        self.runtime_context: RuntimeContext | None = None
        self.task: Task | None = None

    def bind_runtime_context(self, *, runtime_context: RuntimeContext, task: Task) -> None:
        """Bind current runtime context before execution."""
        self.runtime_context = runtime_context
        self.task = task

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for memory."},
                "source": {
                    "type": "string",
                    "enum": ["knowledge", "source_log", "all"],
                    "description": "Which memory source to search.",
                },
                "scope": {
                    "type": "string",
                    "enum": ["auto"],
                    "description": "Currently only auto is supported; scope follows current chat/project session.",
                },
                "limit": {"type": "integer", "description": "Maximum number of results, 1-20."},
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        source: MemorySource = "knowledge",
        scope: str = "auto",
        limit: int = 5,
    ) -> ToolResult:
        if self.runtime_context is None or self.task is None:
            return ToolResult(
                content="memory_retrieve is unavailable outside AgentRuntime",
                success=False,
                error="missing_runtime_context",
            )
        if scope != "auto":
            return ToolResult(
                content="memory_retrieve currently supports only scope='auto'",
                success=False,
                error="unsupported_scope",
            )
        manager = self.memory_manager or self.runtime_context.memory_manager
        if not isinstance(manager, MemoryManager):
            return ToolResult(content="No memory manager is configured", success=False, error="missing_memory_manager")
        matches = retrieve_memory(
            query=query,
            session=self.task.session,
            memory_manager=manager,
            source=source,
            limit=limit,
        )
        if not matches:
            return ToolResult(
                content=f'<memory_results source="{source}" query="{query}" count="0" />',
                metadata={"query": query, "source": source, "scope": scope, "matches": []},
            )
        chunks = [f'<memory_results source="{source}" query="{query}" count="{len(matches)}">']
        metadata_matches = []
        for index, match in enumerate(matches, start=1):
            chunks.append(
                f'<result index="{index}" origin="{match.origin}" score="{match.score}" source="{match.source}">\n'
                f"{match.content}\n"
                "</result>"
            )
            metadata_matches.append(
                {
                    "origin": match.origin,
                    "source": match.source,
                    "score": match.score,
                    "session_id": match.session_id,
                    "task_id": match.task_id,
                }
            )
        chunks.append("</memory_results>")
        return ToolResult(
            content="\n".join(chunks),
            metadata={"query": query, "source": source, "scope": scope, "matches": metadata_matches},
        )
