"""Built-in BKN action execute tool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bamboo.bkn.action_runner import execute_action
from bamboo.bkn.registry import BKNRegistry
from bamboo.bkn.validator import BKNValidationError
from bamboo.tools.buildin.base import Tool, ToolResult

if TYPE_CHECKING:
    from bamboo.factory.task_factory import Task
    from bamboo.runtime.runtime_context import RuntimeContext


class BKNActionExecuteTool(Tool):
    """Execute a BKN-private action script."""

    name = "bkn_action_execute"
    description = "Execute a BKN-private action script under the current platform directory."
    risk_level = "execute"
    tags = ("bkn", "execute", "actions")

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
                "action_id": {"type": "string"},
                "arguments": {"type": "object"},
                "timeout": {"type": "integer"},
            },
            "required": ["platform_id", "action_id"],
        }

    async def execute(
        self,
        platform_id: str,
        action_id: str,
        arguments: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> ToolResult:
        registry = self._registry()
        definition = registry.get(platform_id) if registry else None
        if definition is None:
            return ToolResult(content=f"BKN platform not found: {platform_id}", success=False, error="missing_platform")
        try:
            result = await execute_action(definition, action_id=action_id, arguments=arguments, timeout=timeout)
        except BKNValidationError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        success = int(result["exit_code"]) == 0
        return ToolResult(
            content=f"exit_code={result['exit_code']}\nstdout:\n{result['stdout']}\nstderr:\n{result['stderr']}",
            success=success,
            error="" if success else str(result["stderr"]),
            metadata=result,
        )

    def _registry(self) -> BKNRegistry | None:
        if self.runtime_context is None:
            return None
        return self.runtime_context.bkn_registry
