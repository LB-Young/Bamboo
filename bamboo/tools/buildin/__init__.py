"""Built-in tools for Bamboo."""

from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.buildin.bash import BashTool
from bamboo.tools.buildin.edit import EditTool
from bamboo.tools.buildin.glob import GlobTool
from bamboo.tools.buildin.grep import GrepTool
from bamboo.tools.buildin.read import ReadTool
from bamboo.tools.buildin.skill_load import SkillLoadTool
from bamboo.tools.buildin.write import WriteTool


def create_builtin_tools() -> list[Tool]:
    """创建 Bamboo 随包提供的全部内置工具实例。"""
    return [
        BashTool(),
        EditTool(),
        GlobTool(),
        GrepTool(),
        ReadTool(),
        SkillLoadTool(),
        WriteTool(),
    ]

__all__ = [
    "BashTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "ReadTool",
    "SkillLoadTool",
    "Tool",
    "ToolResult",
    "WriteTool",
    "create_builtin_tools",
]
