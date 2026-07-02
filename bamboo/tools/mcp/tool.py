"""MCP 工具适配器。"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.mcp.client import MCPClient
from bamboo.tools.mcp.models import MCPToolDefinition


class MCPDiscoveredTool(Tool):
    """把单个 MCP tool 包装成 Bamboo 原生工具。"""

    risk_level = "network"
    tags = ("mcp", "network")
    is_builtin = False

    def __init__(self, definition: MCPToolDefinition, client: MCPClient) -> None:
        """保存 MCP tool 定义和 client。"""
        self.definition = definition
        self.client = client
        self.name = mcp_tool_name(definition.server, definition.name)
        self.description = definition.description or f"Call MCP tool {definition.server}/{definition.name}."

    def input_schema(self) -> dict[str, Any]:
        """直接返回 MCP tool 的 input schema。"""
        return self.definition.input_schema or {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: Any) -> ToolResult:
        """调用 MCP tool。"""
        return await asyncio.to_thread(self.client.call_tool, self.definition.name, kwargs)


class MCPProxyTool(Tool):
    """按 server/tool 名称代理调用 MCP tool 的 fallback 工具。"""

    name = "mcp"
    description = "Call a configured MCP server tool by server and tool name."
    risk_level = "network"
    tags = ("mcp", "network")

    def __init__(self, clients: dict[str, MCPClient] | None = None) -> None:
        """保存可用 MCP clients。"""
        self.clients = clients if clients is not None else {}

    def input_schema(self) -> dict[str, Any]:
        """返回代理工具参数 schema。"""
        return {
            "type": "object",
            "properties": {
                "server": {"type": "string", "description": "Configured MCP server name."},
                "tool": {"type": "string", "description": "Tool name exposed by the MCP server."},
                "arguments": {"type": "object", "description": "Tool arguments."},
            },
            "required": ["server", "tool"],
        }

    async def execute(self, server: str, tool: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """调用指定 MCP server 的指定 tool。"""
        client = self.clients.get(server)
        if client is None:
            return ToolResult(
                content=f"MCP server is not configured or not started: {server}",
                success=False,
                error="mcp_server_not_found",
            )
        return await asyncio.to_thread(client.call_tool, tool, arguments or {})


def mcp_tool_name(server: str, tool: str) -> str:
    """把 MCP server/tool 名称转换为 LLM API 兼容工具名。"""
    raw = f"mcp_{server}_{tool}".replace("-", "_").replace(".", "_")
    return re.sub(r"[^A-Za-z0-9_]", "_", raw)
