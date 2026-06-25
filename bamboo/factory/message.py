"""会话消息模型。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from bamboo.llms.base import LLMToolCall

MessageRole = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class Message:
    """表示 Bamboo 会话中的一条消息。"""

    role: MessageRole
    content: str
    agent_name: str = ""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    compressed: bool = False
    origin_message_ids: list[str] = field(default_factory=list)
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    tool_name: str = ""

    def mark_as_compressed(self, origin_message_ids: list[str] | None = None) -> None:
        """标记该历史消息已被摘要替代，并记录可选来源消息。"""
        self.compressed = True
        self.origin_message_ids = origin_message_ids or []
