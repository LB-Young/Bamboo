"""管理 Bamboo 进程内所有来源的工具。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bamboo.tools.buildin.base import Tool


@dataclass(slots=True)
class ToolMetadata:
    """描述工具来源、启用状态和运行风险。"""

    source: str
    enabled: bool = True
    blocked: bool = False
    risk_level: str = "read"
    tags: list[str] = field(default_factory=list)
    registered_at: str = ""


class ToolRegistry:
    """统一注册、查询和管理 Bamboo 工具。"""

    def __init__(self) -> None:
        """初始化空工具注册表。"""
        self._tools: dict[str, Tool] = {}
        self._metadata: dict[str, ToolMetadata] = {}
        self._mcp_clients: dict[str, Any] = {}

    def register(self, tool: Tool, *, source: str) -> None:
        """按工具名注册工具，并记录工具来源。"""
        self._tools[tool.name] = tool
        self._metadata[tool.name] = ToolMetadata(
            source=source,
            risk_level=getattr(tool, "risk_level", "read"),
            tags=list(getattr(tool, "tags", ())),
            registered_at=_utc_now(),
        )

    def register_many(self, tools: list[Tool], *, source: str) -> None:
        """批量注册同一来源的工具。"""
        for tool in tools:
            self.register(tool, source=source)

    def get(self, name: str) -> Tool | None:
        """按名称获取已启用工具；不存在或禁用时返回 None。"""
        metadata = self._metadata.get(name)
        if metadata is None or not metadata.enabled or metadata.blocked:
            return None
        return self._tools[name]

    def get_metadata(self, name: str) -> ToolMetadata | None:
        """返回工具元数据；不存在时返回 None。"""
        return self._metadata.get(name)

    def list_names(self) -> list[str]:
        """按稳定顺序返回所有已注册工具名。"""
        return sorted(self._tools)

    def get_tools(self) -> list[Tool]:
        """返回所有已启用工具。"""
        return [
            self._tools[name]
            for name in self.list_names()
            if self._metadata[name].enabled and not self._metadata[name].blocked
        ]

    def list_by_source(self, source_prefix: str) -> list[Tool]:
        """按来源前缀返回已注册工具。"""
        return [
            self._tools[name]
            for name in self.list_names()
            if self._metadata[name].source.startswith(source_prefix)
        ]

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

    def block(self, name: str) -> bool:
        """阻塞指定工具，不存在时返回 False。"""
        if name not in self._metadata:
            return False
        self._metadata[name].blocked = True
        return True

    def unblock(self, name: str) -> bool:
        """解除工具阻塞，不存在时返回 False。"""
        if name not in self._metadata:
            return False
        self._metadata[name].blocked = False
        return True

    def register_mcp_tools(self, server: str, tools: list[Tool]) -> None:
        """注册指定 MCP server 暴露的工具。"""
        self.register_many(tools, source=f"mcp:{server}")

    def register_plugin_tools(self, plugin_name: str, tools: list[Tool]) -> None:
        """注册指定插件暴露的工具。"""
        self.register_many(tools, source=f"plugin:{plugin_name}")

    def set_mcp_client(self, server: str, client: Any) -> None:
        """保存 MCP server 客户端，供 MCP 工具调用时查找。"""
        self._mcp_clients[server] = client

    def get_mcp_client(self, server: str) -> Any | None:
        """返回已保存的 MCP server 客户端。"""
        return self._mcp_clients.get(server)

    def summary(self) -> dict[str, Any]:
        """返回工具数量、启用状态和来源摘要。"""
        by_source: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for metadata in self._metadata.values():
            by_source[metadata.source] = by_source.get(metadata.source, 0) + 1
            by_risk[metadata.risk_level] = by_risk.get(metadata.risk_level, 0) + 1
        return {
            "total": len(self._tools),
            "enabled": [
                name
                for name in self.list_names()
                if self._metadata[name].enabled and not self._metadata[name].blocked
            ],
            "blocked": [name for name in self.list_names() if self._metadata[name].blocked],
            "sources": {name: self._metadata[name].source for name in self.list_names()},
            "risk_levels": {name: self._metadata[name].risk_level for name in self.list_names()},
            "by_source": by_source,
            "by_risk": by_risk,
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


def _utc_now() -> str:
    """返回 UTC ISO 时间戳。"""
    return datetime.now(UTC).isoformat()
