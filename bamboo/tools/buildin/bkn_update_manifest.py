"""Built-in BKN manifest update tool."""

from __future__ import annotations

from typing import Any

from bamboo.bkn.update import update_manifest
from bamboo.bkn.validator import BKNValidationError
from bamboo.tools.buildin.base import Tool, ToolResult


class BKNUpdateManifestTool(Tool):
    """Update safe manifest fields for an active BKN platform."""

    name = "bkn_update_manifest"
    description = "Update safe fields in a BKN platform manifest after permission approval."
    risk_level = "write"
    tags = ("bkn", "write", "manifest")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "platform_id": {"type": "string"},
                "updates": {"type": "object"},
            },
            "required": ["platform_id", "updates"],
        }

    async def execute(self, platform_id: str, updates: dict[str, Any]) -> ToolResult:
        try:
            result = update_manifest(platform_id=platform_id, updates=updates)
        except BKNValidationError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        return ToolResult(content=f"Updated BKN manifest for {platform_id}", metadata=result)
