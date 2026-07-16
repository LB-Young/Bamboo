"""Built-in BKN topology update tool."""

from __future__ import annotations

from typing import Any

from bamboo.bkn.update import update_topology
from bamboo.bkn.validator import BKNValidationError
from bamboo.tools.buildin.base import Tool, ToolResult


class BKNUpdateTopologyTool(Tool):
    """Update BKN skeleton topology after permission approval."""

    name = "bkn_update_topology"
    description = "Update BKN skeleton nodes and edges. Evidence is required."
    risk_level = "write"
    tags = ("bkn", "write", "topology")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "platform_id": {"type": "string"},
                "nodes": {"type": "array"},
                "edges": {"type": "array"},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["platform_id", "evidence"],
        }

    async def execute(
        self,
        platform_id: str,
        evidence: list[str],
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
    ) -> ToolResult:
        try:
            result = update_topology(platform_id=platform_id, nodes=nodes, edges=edges, evidence=evidence)
        except BKNValidationError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        return ToolResult(content=f"Updated BKN topology for {platform_id}", metadata=result)
