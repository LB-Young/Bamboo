"""Built-in BKN retrieval tool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bamboo.bkn.registry import BKNRegistry
from bamboo.bkn.retrieval import render_bkn_results
from bamboo.factory.task_factory import Task
from bamboo.tools.buildin.base import Tool, ToolResult

if TYPE_CHECKING:
    from bamboo.runtime.runtime_context import RuntimeContext


class BKNRetrievalTool(Tool):
    """Retrieve Bamboo Knowledge Network context on demand."""

    name = "bkn_retrieval"
    description = (
        "Retrieve Bamboo Knowledge Network context for business or platform data. "
        "Use it to find entities, relationships, local dynamic attributes, operators, and available actions."
    )
    risk_level = "read"
    tags = ("bkn", "read", "retrieval")

    def __init__(self, *, bkn_registry: BKNRegistry | None = None) -> None:
        self.bkn_registry = bkn_registry
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
                "query": {
                    "type": "string",
                    "description": "Search query, entity id, platform object, or business question.",
                },
                "network": {
                    "type": "string",
                    "description": "Optional BKN network name. Use auto to search all active networks.",
                },
                "limit": {"type": "integer", "description": "Maximum result count, 1-20."},
                "max_hops": {"type": "integer", "description": "Relationship expansion depth, 0-3."},
                "include_dynamic_data": {
                    "type": "boolean",
                    "description": "Whether to load local dynamic source data when configured.",
                },
                "include_actions": {
                    "type": "boolean",
                    "description": "Whether to include available action metadata.",
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        network: str = "auto",
        limit: int = 5,
        max_hops: int = 2,
        include_dynamic_data: bool = True,
        include_actions: bool = True,
    ) -> ToolResult:
        if self.runtime_context is None or self.task is None:
            return ToolResult(
                content="bkn_retrieval is unavailable outside AgentRuntime",
                success=False,
                error="missing_runtime_context",
            )
        registry = self.bkn_registry or self.runtime_context.bkn_registry
        if not isinstance(registry, BKNRegistry):
            return ToolResult(content="No BKN registry is configured", success=False, error="missing_bkn_registry")
        bounded_limit = max(1, min(int(limit), 20))
        bounded_hops = max(0, min(int(max_hops), 3))
        matches = registry.search(
            query=query,
            network=network,
            limit=bounded_limit,
            max_hops=bounded_hops,
            include_dynamic_data=include_dynamic_data,
            include_actions=include_actions,
        )
        return ToolResult(
            content=render_bkn_results(query=query, network=network, matches=matches),
            metadata={
                "query": query,
                "network": network,
                "limit": bounded_limit,
                "max_hops": bounded_hops,
                "matches": [
                    {
                        "network": match.network,
                        "entity_id": match.entity_id,
                        "entity_class": match.entity_class,
                        "score": match.score,
                        "source_path": match.source_path,
                    }
                    for match in matches
                ],
            },
        )
