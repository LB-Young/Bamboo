"""Bamboo 内置工具注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bamboo.tools.buildin.base import Tool
from bamboo.tools.buildin.bash import BashTool
from bamboo.tools.buildin.edit import EditTool
from bamboo.tools.buildin.glob import GlobTool
from bamboo.tools.buildin.grep import GrepTool
from bamboo.tools.buildin.read import ReadTool
from bamboo.tools.buildin.write import WriteTool


@dataclass(slots=True)
class ToolMetadata:
    """描述工具来源和启用状态。"""

    source: str = "buildin"
    enabled: bool = True


class BuiltinToolRegistry:
    """注册并查询 Bamboo 内置工具。"""

    def __init__(self) -> None:
        """初始化空工具注册表。"""
        self._tools: dict[str, Tool] = {}
        self._metadata: dict[str, ToolMetadata] = {}

    def register(self, tool: Tool, *, source: str = "buildin") -> None:
        """按工具名注册单个工具。"""
        self._tools[tool.name] = tool
        self._metadata[tool.name] = ToolMetadata(source=source)

    def register_many(self, tools: list[Tool], *, source: str = "buildin") -> None:
        """批量注册同一来源的工具。"""
        for tool in tools:
            self.register(tool, source=source)

    def get(self, name: str) -> Tool | None:
        """按名称获取工具；不存在或禁用时返回 None。"""
        metadata = self._metadata.get(name)
        if metadata is not None and not metadata.enabled:
            return None
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        """按稳定顺序返回所有工具名。"""
        return sorted(self._tools)

    def get_tools(self) -> list[Tool]:
        """返回所有已启用工具。"""
        return [self._tools[name] for name in self.list_names() if self._metadata[name].enabled]

    def schemas(self) -> list[dict[str, Any]]:
        """返回所有已启用工具的 schema。"""
        return [tool.schema() for tool in self.get_tools()]

    def enable(self, name: str) -> bool:
        """启用指定工具。"""
        if name not in self._metadata:
            return False
        self._metadata[name].enabled = True
        return True

    def disable(self, name: str) -> bool:
        """禁用指定工具。"""
        if name not in self._metadata:
            return False
        self._metadata[name].enabled = False
        return True

    def summary(self) -> dict[str, Any]:
        """返回用于诊断的注册表摘要。"""
        return {
            "total": len(self._tools),
            "enabled": [name for name in self.list_names() if self._metadata[name].enabled],
            "sources": {name: self._metadata[name].source for name in self.list_names()},
        }


def create_builtin_registry() -> BuiltinToolRegistry:
    """创建并预加载 Bamboo 内置工具注册表。"""
    registry = BuiltinToolRegistry()
    registry.register_many(
        [
            BashTool(),
            EditTool(),
            GlobTool(),
            GrepTool(),
            ReadTool(),
            WriteTool(),
        ]
    )
    return registry


_registry: BuiltinToolRegistry | None = None


def get_builtin_registry() -> BuiltinToolRegistry:
    """获取进程级内置工具注册表单例。"""
    global _registry
    if _registry is None:
        _registry = create_builtin_registry()
    return _registry
