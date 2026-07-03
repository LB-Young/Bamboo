"""Session 数据模型和创建工厂。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bamboo.factory.context import Context
from bamboo.factory.message import Message, MessageRole
from bamboo.helpers.requests_params import RunParams
from bamboo.llms.base import LLMToolCall
from bamboo.memory.session_store import SessionMemoryStore, current_time_record_name
from bamboo.prompts import build_system_prompt, resolve_prompt_mode


@dataclass(slots=True)
class Session:
    """保存单个会话的上下文和消息历史。"""

    session_id: str
    model: str
    provider: str
    context: Context
    messages: list[Message] = field(default_factory=list)
    memory_store: SessionMemoryStore | None = None
    current_task_id: str = ""

    def add_message(
        self,
        role: MessageRole,
        content: str,
        *,
        agent_name: str = "",
        tool_calls: list[LLMToolCall] | None = None,
        tool_call_id: str = "",
        tool_name: str = "",
        message_type: str = "normal",
        active_for_prompt: bool = True,
        origin_message_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        insert_at: int | None = None,
        persist: bool = True,
    ) -> Message:
        """向会话追加一条消息并返回。"""
        message_metadata = dict(metadata or {})
        if self.current_task_id and "task_id" not in message_metadata:
            message_metadata["task_id"] = self.current_task_id
        message = Message(
            role=role,
            content=content,
            agent_name=agent_name,
            tool_calls=tool_calls or [],
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            message_type=message_type,
            active_for_prompt=active_for_prompt,
            origin_message_ids=origin_message_ids or [],
            metadata=message_metadata,
        )
        if insert_at is None:
            self.messages.append(message)
        else:
            self.messages.insert(insert_at, message)
        if persist and self.memory_store is not None:
            self.memory_store.append_message(message, task_id=self.current_task_id)
        return message

    def active_messages(self) -> list[Message]:
        """返回需要继续发送给模型的消息。"""
        return [message for message in self.messages if message.active_for_prompt]

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

        before_snapshots = [
            self.memory_store.message_snapshot(message)
            if self.memory_store is not None
            else self._message_snapshot(message)
            for message in messages
        ]
        summary_message = self.add_message(
            role="system",
            content=f"[conversation-summary]\n{summary}",
            agent_name=agent_name,
            message_type="compaction",
            origin_message_ids=[message.message_id for message in messages],
            metadata={
                "summary": summary,
                "before_message_ids": [message.message_id for message in messages],
                "before_messages": before_snapshots,
            },
            insert_at=min(selected_indexes),
            persist=False,
        )
        after_active_message_ids = [message.message_id for message in self.active_messages()]
        summary_message.metadata["after_active_message_ids"] = after_active_message_ids
        if self.memory_store is not None:
            compaction_payload = self.memory_store.build_compaction_payload(
                selected_messages=messages,
                summary_message=summary_message,
                summary=summary,
                agent_name=agent_name,
                after_active_message_ids=after_active_message_ids,
            )
            self.memory_store.append_compaction(compaction_payload)
            self.memory_store.append_message(
                summary_message,
                task_id=self.current_task_id,
                extra={
                    "subtype": "compaction",
                    "compaction": compaction_payload,
                },
            )
        return summary_message

    @staticmethod
    def _message_snapshot(message: Message) -> dict[str, Any]:
        """生成无需持久化 store 也可使用的消息快照。"""
        return {
            "message_id": message.message_id,
            "time": message.created_at,
            "role": message.role,
            "content": message.content,
            "agent_name": message.agent_name,
            "message_type": message.message_type,
            "active_for_prompt": message.active_for_prompt,
            "compressed": message.compressed,
            "origin_message_ids": list(message.origin_message_ids),
            "metadata": dict(message.metadata),
            "tool_calls": list(message.tool_calls),
            "tool_call_id": message.tool_call_id,
            "tool_name": message.tool_name,
        }

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
        record_dir = self._resolve_record_dir(
            memory_dir_path=memory_dir_path,
            prompt_mode=prompt_mode,
        )
        memory_store = SessionMemoryStore(
            memory_dir=memory_dir_path,
            session_id=run_params.session_id,
            record_dir=record_dir,
        )
        memory_store.save_session(
            mode=prompt_mode,
            project_root=project_root,
            model=run_params.model,
            provider=run_params.provider,
            system_prompt=system_prompt,
            metadata=context.metadata,
        )
        # session保存上下文信息和执行的模型参数
        session = Session(
            session_id=run_params.session_id,
            model=run_params.model,
            provider=run_params.provider,
            context=context,
            memory_store=memory_store,
            current_task_id=run_params.task_id,
        )
        if run_params.message:
            session.add_message("user", run_params.message)
        return session

    def _resolve_record_dir(self, *, memory_dir_path: Path, prompt_mode: str) -> Path:
        """根据模式选择完整对话记录目录名。"""
        return memory_dir_path / current_time_record_name()
