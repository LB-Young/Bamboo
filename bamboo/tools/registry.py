"""管理 Bamboo 进程内所有来源的工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bamboo.tools.buildin.base import Tool


@dataclass(slots=True)
class ToolMetadata:
    """描述工具来源和启用状态。"""

    source: str
    enabled: bool = True


class ToolRegistry:
    """统一注册、查询和管理 Bamboo 工具。"""

    def __init__(self) -> None:
        """初始化空工具注册表。"""
        self._tools: dict[str, Tool] = {}
        self._metadata: dict[str, ToolMetadata] = {}

    def register(self, tool: Tool, *, source: str) -> None:
        """按工具名注册工具，并记录工具来源。"""
        self._tools[tool.name] = tool
        self._metadata[tool.name] = ToolMetadata(source=source)

    def register_many(self, tools: list[Tool], *, source: str) -> None:
        """批量注册同一来源的工具。"""
        for tool in tools:
            self.register(tool, source=source)

    def get(self, name: str) -> Tool | None:
        """按名称获取已启用工具；不存在或禁用时返回 None。"""
        metadata = self._metadata.get(name)
        if metadata is None or not metadata.enabled:
            return None
        return self._tools[name]

    def list_names(self) -> list[str]:
        """按稳定顺序返回所有已注册工具名。"""
        return sorted(self._tools)

    def get_tools(self) -> list[Tool]:
        """返回所有已启用工具。"""
        return [self._tools[name] for name in self.list_names() if self._metadata[name].enabled]

    def schemas(self) -> list[dict[str, Any]]:
        """返回所有已启用工具的模型调用 Schema。"""
        return [tool.schema() for tool in self.get_tools()]

    def enable(self, name: str) -> bool:
        """启用指定工具，不存在时返回 False。"""
        if name not in self._metadata:
            return False
        self._metadata[name].enabled = True
        return True

    def disable(self, name: str) -> bool:
        """禁用指定工具，不存在时返回 False。"""
        if name not in self._metadata:
            return False
        self._metadata[name].enabled = False
        return True

    def summary(self) -> dict[str, Any]:
        """返回工具数量、启用状态和来源摘要。"""
        return {
            "total": len(self._tools),
            "enabled": [name for name in self.list_names() if self._metadata[name].enabled],
            "sources": {name: self._metadata[name].source for name in self.list_names()},
        }


def create_tool_registry() -> ToolRegistry:
    """创建工具注册表，并加载 Bamboo 内置工具。"""
    from bamboo.tools.buildin import create_builtin_tools

    registry = ToolRegistry()
    registry.register_many(create_builtin_tools(), source="buildin")
    return registry


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """返回进程级统一工具注册表。"""
    global _registry
    if _registry is None:
        _registry = create_tool_registry()
    return _registry
