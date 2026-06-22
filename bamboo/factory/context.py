"""Agent 上下文模型。

Context 保存每轮 Agent 执行时需要观察的环境信息，例如项目路径、
memory 路径和系统提示词。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Context:
    """收集 OTA 循环中 Agent 需要的上下文信息。"""

    session_id: str
    project_root: Path
    memory_dir: Path
    system_prompt: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    def build_context(self) -> str:
        """渲染为文本，供 mock Agent 或未来 LLM 调用使用。"""
        return "\n".join(
            [
                f"session_id: {self.session_id}",
                f"project_root: {self.project_root}",
                f"memory_dir: {self.memory_dir}",
                f"system_prompt: {self.system_prompt}",
            ]
        )
