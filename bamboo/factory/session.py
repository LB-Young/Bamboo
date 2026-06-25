"""Session 数据模型和创建工厂。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bamboo.factory.context import Context
from bamboo.factory.message import Message, MessageRole
from bamboo.helpers.requests_params import RunParams
from bamboo.llms.base import LLMToolCall
from bamboo.prompts import build_system_prompt, resolve_prompt_mode


@dataclass(slots=True)
class Session:
    """保存单个会话的上下文和消息历史。"""

    session_id: str
    model: str
    provider: str
    context: Context
    messages: list[Message] = field(default_factory=list)

    def add_message(
        self,
        role: MessageRole,
        content: str,
        *,
        agent_name: str = "",
        tool_calls: list[LLMToolCall] | None = None,
        tool_call_id: str = "",
        tool_name: str = "",
    ) -> Message:
        """向会话追加一条消息并返回。"""
        message = Message(
            role=role,
            content=content,
            agent_name=agent_name,
            tool_calls=tool_calls or [],
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )
        self.messages.append(message)
        return message

    def active_messages(self) -> list[Message]:
        """返回尚未被压缩替代、需要继续发送给模型的消息。"""
        return [message for message in self.messages if not message.compressed]

    def replace_messages_with_summary(
        self,
        messages: list[Message],
        summary: str,
        *,
        agent_name: str,
    ) -> Message:
        """将指定活跃消息标记为已压缩，并在原位置插入摘要消息。"""
        if not messages:
            raise ValueError("At least one message is required for compaction")
        selected_ids = {message.message_id for message in messages}
        selected_indexes = [
            index for index, message in enumerate(self.messages) if message.message_id in selected_ids
        ]
        if len(selected_indexes) != len(selected_ids):
            raise ValueError("Compaction messages must belong to the current session")

        for message in messages:
            if message.compressed:
                raise ValueError("Cannot compact a message that is already compressed")
            message.mark_as_compressed()

        summary_message = Message(
            role="system",
            content=f"[conversation-summary]\n{summary}",
            agent_name=agent_name,
            origin_message_ids=[message.message_id for message in messages],
        )
        self.messages.insert(min(selected_indexes), summary_message)
        return summary_message

    def build_context(self) -> str:
        """渲染当前会话上下文，供 Agent 执行使用。"""
        return self.context.build_context()


class SessionFactory:
    """根据标准化运行参数创建 Session。"""

    def create(self, *, memory_dir_path: Path, run_params: RunParams) -> Session:
        """创建 Session，并写入用户初始消息。"""
        project_root = Path(run_params.project)
        prompt_mode = resolve_prompt_mode(run_params.session_mode, project_root)
        system_prompt = build_system_prompt(
            session_mode=run_params.session_mode,
            project_root=project_root,
            memory_dir=memory_dir_path,
            model=run_params.model,
            provider=run_params.provider,
        )
        # context保存上下文信息
        context = Context(
            session_id=run_params.session_id,
            project_root=project_root,
            memory_dir=memory_dir_path,
            system_prompt=system_prompt,
            metadata={"prompt_mode": prompt_mode},
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
