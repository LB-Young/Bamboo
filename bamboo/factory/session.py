"""Session 数据模型和创建工厂。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bamboo.factory.context import Context
from bamboo.factory.message import Message, MessageRole
from bamboo.helpers.requests_params import RunParams


@dataclass(slots=True)
class Session:
    """保存单个会话的上下文和消息历史。"""

    session_id: str
    model: str
    provider: str
    context: Context
    messages: list[Message] = field(default_factory=list)

    def add_message(self, role: MessageRole, content: str, *, agent_name: str = "") -> Message:
        """向会话追加一条消息并返回。"""
        message = Message(role=role, content=content, agent_name=agent_name)
        self.messages.append(message)
        return message

    def build_context(self) -> str:
        """渲染当前会话上下文，供 Agent 执行使用。"""
        return self.context.build_context()


class SessionFactory:
    """根据标准化运行参数创建 Session。"""

    def create(self, *, memory_dir_path: Path, run_params: RunParams) -> Session:
        """创建 Session，并写入用户初始消息。"""
        # context保存上下文信息
        context = Context(
            session_id=run_params.session_id,
            project_root=Path(run_params.project),
            memory_dir=memory_dir_path,
            system_prompt="You are Bamboo, an AI-powered personal agent assistant.",
        )
        # session保存上下文信息和执行的模型参数
        session = Session(
            session_id=run_params.session_id,
            model=run_params.model,
            provider=run_params.provider,
            context=context,
        )
        if run_params.message:
            session.add_message("user", run_params.message)
        return session
