"""内置 Todo 更新工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bamboo.tools.buildin.base import Tool, ToolResult

TodoStatus = Literal["pending", "in_progress", "completed"]


@dataclass(slots=True)
class TodoItem:
    """表示一条 Agent 可维护的待办项。"""

    id: str
    content: str
    status: TodoStatus


class TodoWriteTool(Tool):
    """更新当前任务的待办列表。"""

    name = "todo_write"
    description = "Replace the current task todo list with structured progress items."
    risk_level = "write"
    tags = ("task", "todo", "write")

    def input_schema(self) -> dict[str, Any]:
        """返回 todo 更新参数 schema。"""
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "The full updated todo list.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Stable todo id."},
                            "content": {"type": "string", "description": "Todo description."},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "Todo progress state.",
                            },
                        },
                        "required": ["id", "content", "status"],
                    },
                }
            },
            "required": ["todos"],
        }

    async def execute(self, todos: list[dict[str, Any]]) -> ToolResult:
        """校验并返回新的 todo 列表。"""
        parsed: list[TodoItem] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(todos):
            if not isinstance(item, dict):
                return ToolResult(
                    content=f"Todo at index {index} must be an object.",
                    success=False,
                    error="invalid_todo",
                )
            todo_id = str(item.get("id", "")).strip()
            content = str(item.get("content", "")).strip()
            status = item.get("status")
            if not todo_id:
                return ToolResult(content=f"Todo at index {index} is missing id.", success=False, error="missing_id")
            if todo_id in seen_ids:
                return ToolResult(content=f"Duplicate todo id: {todo_id}", success=False, error="duplicate_id")
            if not content:
                return ToolResult(
                    content=f"Todo `{todo_id}` must have non-empty content.",
                    success=False,
                    error="empty_content",
                )
            if status not in {"pending", "in_progress", "completed"}:
                return ToolResult(
                    content=f"Todo `{todo_id}` has invalid status: {status}",
                    success=False,
                    error="invalid_status",
                )
            seen_ids.add(todo_id)
            parsed.append(TodoItem(id=todo_id, content=content, status=status))

        in_progress = [item for item in parsed if item.status == "in_progress"]
        if len(in_progress) > 1:
            ids = ", ".join(item.id for item in in_progress)
            return ToolResult(
                content=f"Only one todo can be in_progress at a time: {ids}",
                success=False,
                error="multiple_in_progress",
            )

        counts = {
            "pending": sum(1 for item in parsed if item.status == "pending"),
            "in_progress": len(in_progress),
            "completed": sum(1 for item in parsed if item.status == "completed"),
        }
        lines = [
            f"Updated {len(parsed)} todos.",
            f"pending={counts['pending']} in_progress={counts['in_progress']} completed={counts['completed']}",
        ]
        for item in parsed:
            lines.append(f"- [{item.status}] {item.id}: {item.content}")

        return ToolResult(
            content="\n".join(lines),
            metadata={
                "todos": [
                    {"id": item.id, "content": item.content, "status": item.status}
                    for item in parsed
                ],
                "counts": counts,
            },
        )
