"""MCP 配置和工具定义模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MCPServerConfig:
    """一个 stdio MCP server 的连接配置。"""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout: float = 120.0
    connect_timeout: float = 60.0


@dataclass(slots=True)
class MCPToolDefinition:
    """MCP server 暴露的单个工具定义。"""

    server: str
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
