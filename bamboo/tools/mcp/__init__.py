"""MCP client and Bamboo tool adapters."""

from bamboo.tools.mcp.client import MCPClient
from bamboo.tools.mcp.manager import MCPManager
from bamboo.tools.mcp.models import MCPServerConfig, MCPToolDefinition
from bamboo.tools.mcp.tool import MCPDiscoveredTool, MCPProxyTool

__all__ = [
    "MCPClient",
    "MCPDiscoveredTool",
    "MCPManager",
    "MCPProxyTool",
    "MCPServerConfig",
    "MCPToolDefinition",
]
