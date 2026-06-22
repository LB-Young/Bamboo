"""运行时使用的内存任务存储。

当前 Store 只在进程内保存任务快照，方便主流程和恢复机制跑通。
后续可以替换为文件、SQLite 或其他持久化实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bamboo.factory.task_factory import Task


@dataclass(slots=True)
class TaskSnapshot:
    """保存任务最新可观察状态。"""

    task_id: str
    session_id: str
    status: str
    output: str = ""
    error: str = ""
    history: list[str] = field(default_factory=list)


class InMemoryTaskStore:
    """在当前进程内保存任务状态。"""

    def __init__(self) -> None:
        """初始化空的任务快照存储。"""
        self._tasks: dict[str, TaskSnapshot] = {}

    def save_created(self, task: Task) -> None:
        """记录新创建的任务。"""
        self._tasks[task.task_id] = TaskSnapshot(
            task_id=task.task_id,
            session_id=task.session_id,
            status=task.status,
            output=task.output,
            error=task.error,
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
        snapshot.history.append(status)

    def save_error(self, task: Task, error: str) -> None:
        """记录可恢复或终态任务错误。"""
        snapshot = self._tasks.setdefault(
            task.task_id,
            TaskSnapshot(task_id=task.task_id, session_id=task.session_id, status=task.status),
        )
        snapshot.error = error
        snapshot.history.append(f"error:{error}")

    def get(self, task_id: str) -> TaskSnapshot | None:
        """按 task_id 获取任务快照。"""
        return self._tasks.get(task_id)
