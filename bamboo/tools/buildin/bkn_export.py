"""Built-in BKN export tool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bamboo.bkn.export import BKNExportFormat, export_bkn
from bamboo.bkn.registry import BKNRegistry
from bamboo.tools.buildin.base import Tool, ToolResult

if TYPE_CHECKING:
    from bamboo.factory.task_factory import Task
    from bamboo.runtime.runtime_context import RuntimeContext


class BKNExportTool(Tool):
    """Export a BKN graph or subgraph for inspection."""

    name = "bkn_export"
    description = "Export a Bamboo Knowledge Network graph or node neighborhood as mermaid, dot, or markdown."
    risk_level = "read"
    tags = ("bkn", "read", "export")

    def __init__(self, *, bkn_registry: BKNRegistry | None = None) -> None:
        self.bkn_registry = bkn_registry
        self.runtime_context: RuntimeContext | None = None
        self.task: Task | None = None

    def bind_runtime_context(self, *, runtime_context: RuntimeContext, task: Task) -> None:
        self.runtime_context = runtime_context
        self.task = task

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "network": {"type": "string", "description": "BKN network or platform id to export."},
                "format": {"type": "string", "description": "Output format: mermaid, dot, or markdown."},
                "node": {"type": "string", "description": "Optional node id to export a neighborhood."},
                "depth": {"type": "integer", "description": "Neighborhood depth when node is set, 0-5."},
            },
            "required": ["network"],
        }

    async def execute(
        self,
        network: str,
        format: str = "mermaid",
        node: str = "",
        depth: int = 1,
    ) -> ToolResult:
        registry = self._registry()
        if registry is None:
            return ToolResult(content="No BKN registry is configured", success=False, error="missing_bkn_registry")
        definition = registry.get(network)
        if definition is None:
            return ToolResult(content=f"BKN network not found: {network}", success=False, error="missing_network")
        output_format = _parse_format(format)
        if output_format is None:
            return ToolResult(content=f"Unsupported BKN export format: {format}", success=False, error="bad_format")
        bounded_depth = max(0, min(int(depth), 5))
        content = export_bkn(definition, output_format=output_format, node=node, depth=bounded_depth)
        return ToolResult(
            content=content,
            metadata={
                "network": definition.name,
                "format": output_format,
                "node": node,
                "depth": bounded_depth,
            },
        )

    def _registry(self) -> BKNRegistry | None:
        if self.bkn_registry is not None:
            return self.bkn_registry
        if self.runtime_context is None:
            return None
        return self.runtime_context.bkn_registry


def _parse_format(value: str) -> BKNExportFormat | None:
    normalized = value.strip().lower()
    if normalized in {"mermaid", "dot", "markdown"}:
        return normalized  # type: ignore[return-value]
    return None
