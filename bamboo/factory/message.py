"""会话消息模型。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal


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

    def mark_as_compressed(self, origin_message_ids: list[str] | None = None) -> None:
        """标记该消息为历史消息压缩摘要。"""
        self.compressed = True
        self.origin_message_ids = origin_message_ids or []
