"""Built-in BKN ingest draft tool."""

from __future__ import annotations

from typing import Any

from bamboo.bkn.ingest import create_ingest_draft
from bamboo.bkn.validator import BKNValidationError
from bamboo.tools.buildin.base import Tool, ToolResult


class BKNIngestTool(Tool):
    """Create a staged BKN platform draft."""

    name = "bkn_ingest"
    description = "Create a staged Bamboo Knowledge Network platform draft. It writes draft files only."
    risk_level = "write"
    tags = ("bkn", "write", "ingest")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "platform_id": {"type": "string"},
                "manifest_draft": {"type": "object"},
                "schema": {"type": "object"},
                "nodes": {"type": "array"},
                "edges": {"type": "array"},
                "inputs": {"type": "array"},
            },
            "required": ["platform_id"],
        }

    async def execute(
        self,
        platform_id: str,
        manifest_draft: dict[str, Any] | None = None,
        schema: dict[str, Any] | None = None,
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
        inputs: list[dict[str, Any]] | None = None,
    ) -> ToolResult:
        try:
            result = create_ingest_draft(
                platform_id=platform_id,
                manifest_draft=manifest_draft,
                schema=schema,
                nodes=nodes,
                edges=edges,
                inputs=inputs,
            )
        except BKNValidationError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        return ToolResult(content=f"Created BKN draft for {platform_id}: {result['preview_path']}", metadata=result)
