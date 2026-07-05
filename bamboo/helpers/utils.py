"""Shared helper models."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BaseEvent:
    """所有事件的基类。"""

    type: str
    session_id: str
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_event_id: Optional[str] = None
    step_id: Optional[str] = None
    task_id: Optional[str] = None
    plat_info: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "parent_event_id": self.parent_event_id,
            "step_id": self.step_id,
            "task_id": self.task_id,
            "plat_info": self.plat_info,
        }
