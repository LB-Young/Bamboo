"""验证通用 ToolRegistry 加载和管理内置工具。"""

from bamboo.tools import create_tool_registry


def test_tool_registry_loads_builtin_tools() -> None:
    """验证默认注册表从 buildin 目录加载全部内置工具。"""
    registry = create_tool_registry()
    assert registry.list_names() == ["bash", "edit", "glob", "grep", "read", "write"]
    assert set(registry.summary()["sources"].values()) == {"buildin"}


def test_tool_registry_hides_disabled_tool() -> None:
    """验证禁用工具后名称仍保留，但查询和 Schema 中不再暴露。"""
    registry = create_tool_registry()
    assert registry.disable("bash") is True
    assert registry.get("bash") is None
    assert "bash" in registry.list_names()
    assert "bash" not in {schema["name"] for schema in registry.schemas()}
