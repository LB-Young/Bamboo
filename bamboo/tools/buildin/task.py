"""内置任务快照管理工具。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from bamboo.runtime.store import TaskSnapshot, get_task_store
from bamboo.tools.buildin.base import Tool, ToolResult


def _snapshot_payload(snapshot: TaskSnapshot) -> dict[str, Any]:
    """把任务快照转换为工具 metadata 使用的字典。"""
    return {
        "task_id": snapshot.task_id,
        "session_id": snapshot.session_id,
        "status": snapshot.status,
        "title": snapshot.title,
        "description": snapshot.description,
        "output": snapshot.output,
        "error": snapshot.error,
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
        "metadata": snapshot.metadata,
        "history": snapshot.history,
    }


def _snapshot_text(snapshot: TaskSnapshot) -> str:
    """把任务快照格式化为简短文本。"""
    lines = [
        f"task_id: {snapshot.task_id}",
        f"status: {snapshot.status}",
        f"title: {snapshot.title}",
    ]
    if snapshot.session_id:
        lines.append(f"session_id: {snapshot.session_id}")
    if snapshot.description:
        lines.append(f"description: {snapshot.description}")
    if snapshot.error:
        lines.append(f"error: {snapshot.error}")
    return "\n".join(lines)


class TaskCreateTool(Tool):
    """创建一个进程内任务快照。"""

    name = "task_create"
    description = "Create a task snapshot for tracking long-running or delegated work."
    risk_level = "write"
    tags = ("task", "write")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short task title."},
                "description": {"type": "string", "description": "Detailed task instructions."},
                "session_id": {"type": "string", "description": "Optional owning session id."},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for organizing tasks.",
                },
                "depends_on": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional task ids that this task depends on.",
                },
            },
            "required": ["title"],
        }

    async def execute(
        self,
        title: str,
        description: str = "",
        session_id: str = "",
        tags: list[str] | None = None,
        depends_on: list[str] | None = None,
    ) -> ToolResult:
        if not title.strip():
            return ToolResult(content="Task title must not be empty.", success=False, error="empty_title")
        task_id = str(uuid4())
        snapshot = get_task_store().create_task(
            task_id=task_id,
            session_id=session_id,
            title=title.strip(),
            description=description.strip(),
            metadata={
                "tags": list(tags or []),
                "depends_on": list(depends_on or []),
                "created_by": "tool",
            },
        )
        return ToolResult(
            content=f"Created task `{snapshot.task_id}`.\n{_snapshot_text(snapshot)}",
            metadata={"task": _snapshot_payload(snapshot)},
        )


class TaskGetTool(Tool):
    """按 task_id 获取任务快照。"""

    name = "task_get"
    description = "Get a task snapshot by task_id."
    risk_level = "read"
    tags = ("task", "read")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task id to retrieve."},
            },
            "required": ["task_id"],
        }

    async def execute(self, task_id: str) -> ToolResult:
        snapshot = get_task_store().get(task_id)
        if snapshot is None:
            return ToolResult(content=f"Task not found: {task_id}", success=False, error="task_not_found")
        return ToolResult(content=_snapshot_text(snapshot), metadata={"task": _snapshot_payload(snapshot)})


class TaskListTool(Tool):
    """列出任务快照。"""

    name = "task_list"
    description = "List task snapshots, optionally filtered by session_id or status."
    risk_level = "read"
    tags = ("task", "read")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Optional session id filter."},
                "status": {"type": "string", "description": "Optional status filter."},
            },
            "required": [],
        }

    async def execute(self, session_id: str = "", status: str = "") -> ToolResult:
        snapshots = get_task_store().list(session_id=session_id or None, status=status or None)
        if not snapshots:
            return ToolResult(content="(no tasks)", metadata={"tasks": []})
        lines = [
            f"{snapshot.task_id} [{snapshot.status}] {snapshot.title}"
            for snapshot in snapshots
        ]
        return ToolResult(
            content="\n".join(lines),
            metadata={"tasks": [_snapshot_payload(snapshot) for snapshot in snapshots]},
        )


class TaskStopTool(Tool):
    """把任务标记为 cancelled。"""

    name = "task_stop"
    description = "Mark a task snapshot as cancelled."
    risk_level = "write"
    tags = ("task", "write")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task id to stop."},
                "reason": {"type": "string", "description": "Reason for stopping the task."},
            },
            "required": ["task_id"],
        }

    async def execute(self, task_id: str, reason: str = "") -> ToolResult:
        snapshot = get_task_store().stop(task_id, reason)
        if snapshot is None:
            return ToolResult(content=f"Task not found: {task_id}", success=False, error="task_not_found")
        return ToolResult(
            content=f"Cancelled task `{task_id}`.\n{_snapshot_text(snapshot)}",
            metadata={"task": _snapshot_payload(snapshot)},
        )
