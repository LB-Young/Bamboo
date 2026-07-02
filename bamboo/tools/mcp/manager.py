"""MCP server 管理和工具注册。"""

from __future__ import annotations

from typing import Any

from bamboo.tools import ToolRegistry
from bamboo.tools.mcp.client import MCPClient
from bamboo.tools.mcp.models import MCPServerConfig
from bamboo.tools.mcp.tool import MCPDiscoveredTool, MCPProxyTool


class MCPManager:
    """管理多个 stdio MCP server。"""

    def __init__(self, configs: list[MCPServerConfig]) -> None:
        """保存 MCP server 配置。"""
        self.configs = configs
        self.clients: dict[str, MCPClient] = {}
        self.errors: dict[str, str] = {}

    @classmethod
    def from_config(cls, document: dict[str, Any] | None) -> MCPManager:
        """从 mcp.yaml 内容创建 manager。"""
        raw = document or {}
        mcp_config = raw.get("mcp", raw)
        if not isinstance(mcp_config, dict) or not mcp_config.get("auto_start", False):
            return cls([])
        raw_servers = mcp_config.get("servers", {})
        configs: list[MCPServerConfig] = []
        if isinstance(raw_servers, dict):
            iterable = raw_servers.items()
        elif isinstance(raw_servers, list):
            iterable = ((str(item.get("name", "")), item) for item in raw_servers if isinstance(item, dict))
        else:
            iterable = []
        for name, raw_server in iterable:
            if not isinstance(raw_server, dict):
                continue
            command = raw_server.get("command")
            if not isinstance(name, str) or not name or not isinstance(command, str) or not command:
                continue
            args = raw_server.get("args", [])
            env = raw_server.get("env", {})
            configs.append(
                MCPServerConfig(
                    name=name,
                    command=command,
                    args=list(args) if isinstance(args, list) else [],
                    env=dict(env) if isinstance(env, dict) else {},
                    timeout=float(raw_server.get("timeout", 120)),
                    connect_timeout=float(raw_server.get("connect_timeout", 60)),
                )
            )
        return cls(configs)

    def start_all(self) -> None:
        """启动所有配置的 MCP server。"""
        for config in self.configs:
            client = MCPClient(config)
            try:
                client.start()
            except Exception as exc:
                self.errors[config.name] = str(exc)
                continue
            self.clients[config.name] = client

    def register_tools(self, registry: ToolRegistry) -> None:
        """把发现到的 MCP tools 注册为 Bamboo 原生工具。"""
        if self.clients:
            registry.register(MCPProxyTool(self.clients), source="mcp")
        for server, client in self.clients.items():
            registry.set_mcp_client(server, client)
            registry.register_mcp_tools(server, [MCPDiscoveredTool(tool, client) for tool in client.tools])

    def stop_all(self) -> None:
        """停止所有 MCP server。"""
        for client in list(self.clients.values()):
            client.stop()
        self.clients.clear()
