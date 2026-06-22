"""Bamboo 内置工具的基础抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolResult:
    """表示工具执行后的标准化结果。"""

    content: str
    success: bool = True
    error: str = ""
    metadata: dict[str, Any] | None = None


class Tool(ABC):
    """所有内置工具都需要实现的接口。"""

    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具并返回标准化结果。"""

    def schema(self) -> dict[str, Any]:
        """返回 Agent 或模型调用该工具所需的 schema。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
        }

    def input_schema(self) -> dict[str, Any]:
        """返回工具参数的类 JSON Schema 描述。"""
        return {"type": "object", "properties": {}, "required": []}
