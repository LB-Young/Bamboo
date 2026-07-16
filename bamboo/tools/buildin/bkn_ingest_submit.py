"""Built-in BKN ingest submit tool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bamboo.bkn.ingest import submit_ingest_draft
from bamboo.bkn.validator import BKNValidationError
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import AuditEvent
from bamboo.tools.buildin.base import Tool, ToolResult

if TYPE_CHECKING:
    from bamboo.runtime.runtime_context import RuntimeContext


class BKNIngestSubmitTool(Tool):
    """Submit a staged BKN platform draft."""

    name = "bkn_ingest_submit"
    description = "Submit an approved BKN platform draft into the active platform directory."
    risk_level = "write"
    tags = ("bkn", "write", "ingest")

    def __init__(self) -> None:
        self.runtime_context: RuntimeContext | None = None
        self.task: Task | None = None

    def bind_runtime_context(self, *, runtime_context: RuntimeContext, task: Task) -> None:
        self.runtime_context = runtime_context
        self.task = task

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "platform_id": {"type": "string"},
                "approve": {"type": "boolean"},
                "edits": {"type": "object"},
            },
            "required": ["platform_id", "approve"],
        }

    async def execute(self, platform_id: str, approve: bool, edits: dict[str, Any] | None = None) -> ToolResult:
        try:
            result = submit_ingest_draft(platform_id=platform_id, approve=approve, edits=edits)
        except BKNValidationError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        if result.get("submitted") and self.runtime_context is not None and self.task is not None:
            await self.runtime_context.event_bus.emit(
                AuditEvent(
                    session_id=self.task.session_id,
                    task_id=self.task.task_id,
                    action="bkn.platform.activated",
                    tool_name=self.name,
                    params={"platform_id": platform_id},
                    result=str(result.get("platform_root", "")),
                    approved=True,
                )
            )
        return ToolResult(content=f"BKN draft submit result: {result}", metadata=result)
