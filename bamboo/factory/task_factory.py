"""Task 数据模型和创建工厂。

TaskFactory 只做对象创建：根据 RunParams 创建 Task、Session、Context，
不执行 Agent，也不发布 EventBus 事件。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from bamboo.factory.session import Session, SessionFactory
from bamboo.helpers.config import BambooConfig
from bamboo.helpers.requests_params import RunParams
from bamboo.memory.get_memory_path import get_date_memory_path, get_project_memory_path


TaskStatus = Literal["created", "running", "completed", "failed", "cancelled"]


@dataclass(slots=True)
class Task:
    """表示一次用户请求在运行时中的任务实体。"""

    platform: str
    session_id: str
    task_id: str
    user_query: str
    session: Session
    config: BambooConfig
    run_params: RunParams
    memory_dir: Path
    status: TaskStatus = "created"
    output: str = ""
    error: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def session_obj(self) -> Session:
        """兼容旧代码里的 session_obj 命名。"""
        return self.session


class TaskFactory:
    """创建 Task 对象，但不负责执行。"""

    def __init__(
        self,
        *,
        config: BambooConfig | None = None,
        session_factory: SessionFactory | None = None,
    ) -> None:
        """初始化工厂依赖。"""
        self.config = config or BambooConfig()
        self.session_factory = session_factory or SessionFactory()

    def create(self, run_params: RunParams) -> Task:
        """根据标准化运行参数创建 Task、Session 和 Context。"""
        memory_dir = self._resolve_memory_dir(run_params)
        session = self.session_factory.create(memory_dir_path=memory_dir, run_params=run_params)
        return Task(
            platform=run_params.platform,
            session_id=run_params.session_id,
            task_id=run_params.task_id,
            user_query=run_params.user_query,
            session=session,
            config=self.config,
            run_params=run_params,
            memory_dir=memory_dir,
        )

    def _resolve_memory_dir(self, run_params: RunParams) -> Path:
        """根据会话模式选择 memory 目录。"""
        session_mode = run_params.session_mode_value
        if session_mode == "project":
            return get_project_memory_path(run_params.project)
        if session_mode in {"chat", "auto", ""}:
            return get_date_memory_path()
        raise ValueError(f"Unsupported session mode: {session_mode}")
