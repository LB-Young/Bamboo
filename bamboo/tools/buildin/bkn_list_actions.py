"""Built-in BKN action listing tool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bamboo.bkn.action_runner import list_actions
from bamboo.bkn.registry import BKNRegistry
from bamboo.tools.buildin.base import Tool, ToolResult

if TYPE_CHECKING:
    from bamboo.factory.task_factory import Task
    from bamboo.runtime.runtime_context import RuntimeContext


class BKNListActionsTool(Tool):
    """List BKN-private actions for a platform."""

    name = "bkn_list_actions"
    description = "List BKN-private actions allowed for a platform and optional ontology class."
    risk_level = "read"
    tags = ("bkn", "read", "actions")

    def __init__(self) -> None:
        self.runtime_context: RuntimeContext | None = None
        self.task: Task | None = None

    def bind_runtime_context(self, *, runtime_context: RuntimeContext, task: Task) -> None:
        self.runtime_context = runtime_context
        self.task = task

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"platform_id": {"type": "string"}, "entity_class": {"type": "string"}},
            "required": ["platform_id"],
        }

    async def execute(self, platform_id: str, entity_class: str = "") -> ToolResult:
        registry = self._registry()
        definition = registry.get(platform_id) if registry else None
        if definition is None:
            return ToolResult(content=f"BKN platform not found: {platform_id}", success=False, error="missing_platform")
        actions = list_actions(definition, entity_class=entity_class or None)
        return ToolResult(
            content="\n".join(f"- {action.name}: {action.description}" for action in actions)
            or f"No BKN actions available for {platform_id}",
            metadata={"platform_id": platform_id, "actions": [{"name": action.name, "description": action.description} for action in actions]},
        )

    def _registry(self) -> BKNRegistry | None:
        if self.runtime_context is None:
            return None
        return self.runtime_context.bkn_registry
