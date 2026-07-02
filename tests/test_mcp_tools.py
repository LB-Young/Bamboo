"""验证 MCP stdio client、manager 和工具注册。"""

from __future__ import annotations

import sys
from pathlib import Path

import anyio

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.tools import ToolRegistry
from bamboo.tools.mcp import MCPClient, MCPManager, MCPServerConfig
from bamboo.tools.mcp.tool import mcp_tool_name


def test_mcp_client_lists_and_calls_tools(tmp_path: Path) -> None:
    """验证 MCPClient 可以 initialize、tools/list 和 tools/call。"""
    server = _write_fake_mcp_server(tmp_path)
    client = MCPClient(MCPServerConfig(name="time", command=sys.executable, args=[str(server)]))

    try:
        client.start()
        assert [tool.name for tool in client.tools] == ["now"]
        result = client.call_tool("now", {"zone": "UTC"})
        assert result.success is True
        assert result.content == "time in UTC"
    finally:
        client.stop()


def test_mcp_manager_registers_discovered_tools(tmp_path: Path) -> None:
    """验证 manager 将 MCP tools 注册为 Bamboo 原生工具。"""
    server = _write_fake_mcp_server(tmp_path)
    document = {
        "mcp": {
            "auto_start": True,
            "servers": {
                "time": {
                    "command": sys.executable,
                    "args": [str(server)],
                }
            },
        }
    }
    manager = MCPManager.from_config(document)
    registry = ToolRegistry()

    try:
        manager.start_all()
        manager.register_tools(registry)

        assert registry.get("mcp") is not None
        tool_name = mcp_tool_name("time", "now")
        tool = registry.get(tool_name)
        assert tool is not None
        assert registry.get_metadata(tool_name).source == "mcp:time"  # type: ignore[union-attr]
        assert registry.get_metadata(tool_name).risk_level == "network"  # type: ignore[union-attr]
        assert registry.get_mcp_client("time") is manager.clients["time"]

        async def run_test() -> None:
            result = await tool.execute(zone="Asia/Shanghai")  # type: ignore[union-attr]
            assert result.content == "time in Asia/Shanghai"

        anyio.run(run_test)
    finally:
        manager.stop_all()


def test_runtime_context_builder_loads_mcp_tools(tmp_path: Path) -> None:
    """验证 RuntimeContextBuilder 会按 task config 注册 MCP tools。"""
    server = _write_fake_mcp_server(tmp_path)
    config = _ConfigWithMCP(server)
    task = TaskFactory(config=config).create(RunParams(message="hello", model="agent-model"))
    llm_factory = LLMFactory.from_mapping(config.get("models"))
    event_bus = EventBus()
    registry = ToolRegistry()
    builder = RuntimeContextBuilder(event_bus=event_bus, llm_factory=llm_factory, tool_registry=registry)

    context = builder.build(task)
    try:
        assert context.mcp_manager is not None
        assert "time" in context.mcp_manager.clients
        assert registry.get(mcp_tool_name("time", "now")) is not None
        assert registry.get("mcp") is not None
    finally:
        context.mcp_manager.stop_all()  # type: ignore[union-attr]


def test_mcp_manager_ignores_disabled_config() -> None:
    """验证 auto_start=false 时不会创建 server config。"""
    manager = MCPManager.from_config({"mcp": {"auto_start": False, "servers": {"x": {"command": "nope"}}}})
    assert manager.configs == []


def _write_fake_mcp_server(tmp_path: Path) -> Path:
    """写入一个 newline JSON-RPC fake MCP server。"""
    server = tmp_path / "fake_mcp_server.py"
    server.write_text(
        """
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if "id" not in request:
        continue
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {}}
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "now",
                    "description": "Return the current time.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"zone": {"type": "string"}},
                        "required": ["zone"],
                    },
                }
            ]
        }
    elif method == "tools/call":
        zone = request.get("params", {}).get("arguments", {}).get("zone", "")
        result = {"content": [{"type": "text", "text": f"time in {zone}"}]}
    else:
        result = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}) + "\\n")
    sys.stdout.flush()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return server


class _ConfigWithMCP:
    """RuntimeContextBuilder 测试用配置。"""

    def __init__(self, server: Path) -> None:
        self.server = server

    def get(self, name: str, default: object = None) -> object:
        if name == "models":
            return {
                "default_model": "agent-model",
                "models": {
                    "agent-model": {
                        "provider": "deepseek",
                        "model": "provider-model-id",
                        "api_key": "test-api-key",
                        "base_url": "https://llm.test/v1",
                        "max_tokens": 128,
                    }
                },
            }
        if name == "mcp":
            return {
                "mcp": {
                    "auto_start": True,
                    "servers": {
                        "time": {
                            "command": sys.executable,
                            "args": [str(self.server)],
                        }
                    },
                }
            }
        return default
