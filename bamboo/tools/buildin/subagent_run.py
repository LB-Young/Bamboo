"""Built-in tool for delegating work to a restricted subagent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bamboo.factory.task_factory import Task
from bamboo.subagents import SubagentRegistry
from bamboo.tools.buildin.base import Tool, ToolResult

if TYPE_CHECKING:
    from bamboo.runtime.runtime_context import RuntimeContext


class SubagentRunTool(Tool):
    """Run a same-process restricted subagent."""

    name = "subagent_run"
    description = "Delegate a focused subtask to a restricted Bamboo subagent."
    risk_level = "read"
    tags = ("subagent", "delegate", "read")

    def __init__(self, *, subagent_registry: SubagentRegistry | None = None) -> None:
        self.subagent_registry = subagent_registry
        self.runtime_context: RuntimeContext | None = None
        self.parent_task: Task | None = None

    def bind_runtime_context(self, *, runtime_context: RuntimeContext, task: Task) -> None:
        """Bind parent runtime context before execution."""
        self.runtime_context = runtime_context
        self.parent_task = task

    def input_schema(self) -> dict[str, Any]:
        """Return subagent delegation schema."""
        return {
            "type": "object",
            "properties": {
                "subagent_type": {
                    "type": "string",
                    "description": "Subagent profile name, for example explorer, planner, verifier, or reviewer.",
                },
                "description": {"type": "string", "description": "Short description of the delegated task."},
                "prompt": {"type": "string", "description": "Detailed instructions for the subagent."},
                "task_id": {"type": "string", "description": "Optional child task id."},
            },
            "required": ["subagent_type", "description", "prompt"],
        }

    async def execute(
        self,
        subagent_type: str,
        description: str,
        prompt: str,
        task_id: str | None = None,
    ) -> ToolResult:
        """Run the requested subagent and return a compact task result."""
        if self.runtime_context is None or self.parent_task is None:
            return ToolResult(
                content="subagent_run is unavailable outside AgentRuntime",
                success=False,
                error="missing_runtime_context",
            )
        registry = self.subagent_registry or self.runtime_context.subagent_registry
        if registry is None:
            return ToolResult(
                content="No subagent registry is configured",
                success=False,
                error="missing_subagent_registry",
            )
        from bamboo.runtime.subagent_runtime import SubagentRuntime

        runtime = SubagentRuntime(
            parent_context=self.runtime_context,
            parent_task=self.parent_task,
            registry=registry,
        )
        try:
            result = await runtime.run(
                subagent_type=subagent_type,
                description=description,
                prompt=prompt,
                task_id=task_id,
            )
        except Exception as exc:
            return ToolResult(content=f"Subagent failed: {exc}", success=False, error=str(exc))
        content = (
            f'<task_result subagent="{result.subagent_name}" '
            f'task_id="{result.task_id}" session_id="{result.session_id}" status="{result.status}">\n'
            f"{result.output}\n"
            "</task_result>"
        )
        return ToolResult(
            content=content,
            metadata={
                "subagent_name": result.subagent_name,
                "task_id": result.task_id,
                "session_id": result.session_id,
                "status": result.status,
            },
        )
