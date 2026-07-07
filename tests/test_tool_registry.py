"""验证通用 ToolRegistry 加载和管理内置工具。"""

from typing import Any

from bamboo.tools import ToolRegistry, create_tool_registry
from bamboo.tools.buildin.base import Tool, ToolResult


def test_tool_registry_loads_builtin_tools() -> None:
    """验证默认注册表从 buildin 目录加载全部内置工具。"""
    registry = create_tool_registry()
    assert registry.list_names() == [
        "bash",
        "browser",
        "cron_add",
        "cron_disable",
        "cron_enable",
        "cron_get",
        "cron_list",
        "cron_runs",
        "cron_tick",
        "edit",
        "glob",
        "grep",
        "lsp",
        "memory_backfill",
        "memory_read",
        "memory_retrieve",
        "memory_search",
        "memory_update",
        "read",
        "skill_installer",
        "skill_load",
        "subagent_run",
        "task_create",
        "task_get",
        "task_list",
        "task_stop",
        "todo_write",
        "web_fetch",
        "workflow_installer",
        "workflow_load",
        "workflow_run",
        "write",
    ]
    assert set(registry.summary()["sources"].values()) == {"buildin"}
    assert registry.summary()["by_source"] == {"buildin": 32}
    assert registry.summary()["by_risk"] == {"execute": 2, "network": 1, "read": 15, "unknown": 1, "write": 13}


def test_tool_registry_hides_disabled_tool() -> None:
    """验证禁用工具后名称仍保留，但查询和 Schema 中不再暴露。"""
    registry = create_tool_registry()
    assert registry.disable("bash") is True
    assert registry.get("bash") is None
    assert "bash" in registry.list_names()
    assert "bash" not in {schema["name"] for schema in registry.schemas()}


def test_tool_registry_records_metadata_without_polluting_schema() -> None:
    """验证风险元数据只保存在注册表，不进入模型 tool schema。"""
    registry = create_tool_registry()
    metadata = registry.get_metadata("write")
    assert metadata is not None
    assert metadata.source == "buildin"
    assert metadata.risk_level == "write"
    assert metadata.tags == ["filesystem", "write"]
    assert metadata.registered_at

    write_schema = next(schema for schema in registry.schemas() if schema["name"] == "write")
    assert "risk_level" not in write_schema
    assert "tags" not in write_schema


def test_tool_registry_blocks_and_unblocks_tool() -> None:
    """验证 block 是用户级阻塞，不改变注册名称和 enable 状态。"""
    registry = create_tool_registry()
    assert registry.block("bash") is True
    assert registry.get("bash") is None
    assert "bash" in registry.list_names()
    assert "bash" not in {schema["name"] for schema in registry.schemas()}
    assert registry.summary()["blocked"] == ["bash"]

    assert registry.unblock("bash") is True
    assert registry.get("bash") is not None
    assert registry.summary()["blocked"] == []


def test_tool_registry_filters_tools_by_source() -> None:
    """验证 MCP 和插件来源可以按前缀筛选。"""
    registry = ToolRegistry()
    mcp_tool = _DummyTool(name="mcp_time_now", risk_level="network")
    plugin_tool = _DummyTool(name="plugin_echo", risk_level="execute")

    registry.register_mcp_tools("time", [mcp_tool])
    registry.register_plugin_tools("demo", [plugin_tool])

    assert [tool.name for tool in registry.list_by_source("mcp:")] == ["mcp_time_now"]
    assert [tool.name for tool in registry.list_by_source("plugin:demo")] == ["plugin_echo"]
    assert registry.get_metadata("mcp_time_now").source == "mcp:time"  # type: ignore[union-attr]
    assert registry.get_metadata("mcp_time_now").risk_level == "network"  # type: ignore[union-attr]


def test_tool_registry_stores_mcp_clients() -> None:
    """验证 MCP client 可按 server 名保存和读取。"""
    registry = ToolRegistry()
    client = object()
    registry.set_mcp_client("github", client)
    assert registry.get_mcp_client("github") is client
    assert registry.get_mcp_client("missing") is None


class _DummyTool(Tool):
    """测试用工具。"""

    description = "dummy tool"

    def __init__(self, *, name: str, risk_level: str = "read") -> None:
        self.name = name
        self.risk_level = risk_level
        self.tags = ("dummy",)

    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(content="ok")
