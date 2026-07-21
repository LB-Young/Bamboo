"""入口请求参数模型。

RunParams 是 Adapter 和 Runtime 之间的稳定数据边界。不同入口
可以有不同参数形式，但进入运行时之前都应归一化为 RunParams。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from bamboo.helpers.constant import SessionMode
from bamboo.llms.base import LLMImage
from bamboo.llms.media import images_from_text, merge_images


@dataclass(slots=True)
class RunParams:
    """承载从 Adapter 传入 Runtime 的标准化输入。"""

    platform: str = "cli"
    message: str = ""
    images: list[LLMImage] = field(default_factory=list)
    project: str = field(default_factory=lambda: str(Path.cwd()))
    model: str = ""
    provider: str = ""
    permission: str = "default"
    no_stream: bool = False
    yes_all: bool = False
    debug_events: bool = False
    verbosity: str = "simple"
    session_mode: SessionMode | str = SessionMode.chat
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        """Attach image paths mentioned directly in the user message."""
        self.images = merge_images(self.images, images_from_text(self.message))

    @classmethod
    def from_cli(
        cls,
        *,
        message: str = "",
        images: list[LLMImage] | None = None,
        project: str | Path | None = None,
        model: str | None = None,
        provider: str | None = None,
        permission: str | None = None,
        no_stream: bool = False,
        yes_all: bool = False,
        debug_events: bool = False,
        verbosity: str = "simple",
        session_mode: SessionMode | str = SessionMode.chat,
    ) -> RunParams:
        """根据 CLI 参数创建标准化运行参数。"""
        return cls(
            platform="cli",
            message=message or "",
            images=merge_images(images or [], images_from_text(message or "")),
            project=str(project or Path.cwd()),
            model=model or "",
            provider=provider or "",
            permission=permission or "default",
            no_stream=no_stream,
            yes_all=yes_all,
            debug_events=debug_events,
            verbosity=verbosity,
            session_mode=session_mode,
        )

    @property
    def user_query(self) -> str:
        """以任务领域命名暴露用户输入文本。"""
        return self.message

    @property
    def session_mode_value(self) -> str:
        """返回字符串形式的会话模式。"""
        return getattr(self.session_mode, "value", self.session_mode) or SessionMode.chat.value

    @property
    def platfrom(self) -> str:
        """兼容历史拼写错误字段 platfrom。"""
        return self.platform

    @platfrom.setter
    def platfrom(self, value: str) -> None:
        """把历史拼写错误字段映射回 platform。"""
        self.platform = value
