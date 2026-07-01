"""运行时使用的内存任务存储。

当前 Store 只在进程内保存任务快照，方便主流程和恢复机制跑通。
后续可以替换为文件、SQLite 或其他持久化实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bamboo.factory.task_factory import Task


def utc_now() -> str:
    """返回 UTC ISO 时间戳。"""
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class TaskSnapshot:
    """保存任务最新可观察状态。"""

    task_id: str
    session_id: str
    status: str
    title: str = ""
    description: str = ""
    output: str = ""
    error: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)


class InMemoryTaskStore:
    """在当前进程内保存任务状态。"""

    def __init__(self) -> None:
        """初始化空的任务快照存储。"""
        self._tasks: dict[str, TaskSnapshot] = {}

    def save_created(self, task: Task) -> None:
        """记录新创建的任务。"""
        now = utc_now()
        self._tasks[task.task_id] = TaskSnapshot(
            task_id=task.task_id,
            session_id=task.session_id,
            status=task.status,
            title=(task.user_query or task.task_id)[:80],
            output=task.output,
            error=task.error,
            created_at=now,
            updated_at=now,
            metadata=dict(task.metadata),
            history=[task.status],
        )

    def save_status(self, task: Task, status: str) -> None:
        """更新任务状态快照。"""
        snapshot = self._tasks.setdefault(
            task.task_id,
            TaskSnapshot(task_id=task.task_id, session_id=task.session_id, status=status),
        )
        snapshot.status = status
        snapshot.output = task.output
        snapshot.error = task.error
        snapshot.updated_at = utc_now()
        snapshot.metadata.update(task.metadata)
        snapshot.history.append(status)

    def save_error(self, task: Task, error: str) -> None:
        """记录可恢复或终态任务错误。"""
        snapshot = self._tasks.setdefault(
            task.task_id,
            TaskSnapshot(task_id=task.task_id, session_id=task.session_id, status=task.status),
        )
        snapshot.error = error
        snapshot.updated_at = utc_now()
        snapshot.metadata.update(task.metadata)
        snapshot.history.append(f"error:{error}")

    def create_task(
        self,
        *,
        task_id: str,
        session_id: str = "",
        title: str = "",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TaskSnapshot:
        """创建一个工具级任务快照。"""
        now = utc_now()
        snapshot = TaskSnapshot(
            task_id=task_id,
            session_id=session_id,
            status="created",
            title=title or task_id,
            description=description,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            history=["created"],
        )
        self._tasks[task_id] = snapshot
        return snapshot

    def list(
        self,
        *,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[TaskSnapshot]:
        """返回任务快照列表，可按 session_id 或 status 过滤。"""
        snapshots = list(self._tasks.values())
        if session_id:
            snapshots = [snapshot for snapshot in snapshots if snapshot.session_id == session_id]
        if status:
            snapshots = [snapshot for snapshot in snapshots if snapshot.status == status]
        return sorted(snapshots, key=lambda snapshot: snapshot.updated_at or snapshot.created_at)

    def stop(self, task_id: str, reason: str = "") -> TaskSnapshot | None:
        """把任务标记为 cancelled。"""
        snapshot = self._tasks.get(task_id)
        if snapshot is None:
            return None
        snapshot.status = "cancelled"
        snapshot.error = reason
        snapshot.updated_at = utc_now()
        snapshot.history.append("cancelled")
        if reason:
            snapshot.metadata["stop_reason"] = reason
        return snapshot

    def save_metadata(self, task_id: str, metadata: dict[str, Any]) -> None:
        """更新指定任务的 metadata。"""
        snapshot = self._tasks.get(task_id)
        if snapshot is None:
            return
        snapshot.metadata.update(metadata)
        snapshot.updated_at = utc_now()

    def get(self, task_id: str) -> TaskSnapshot | None:
        """按 task_id 获取任务快照。"""
        return self._tasks.get(task_id)


_task_store: InMemoryTaskStore | None = None


def get_task_store() -> InMemoryTaskStore:
    """返回进程级默认任务存储。"""
    global _task_store
    if _task_store is None:
        _task_store = InMemoryTaskStore()
    return _task_store


def reset_task_store() -> None:
    """重置进程级任务存储，主要用于测试。"""
    global _task_store
    _task_store = InMemoryTaskStore()
