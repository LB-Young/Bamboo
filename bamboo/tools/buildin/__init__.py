"""Built-in tools for Bamboo."""

from bamboo.tools.buildin.base import Tool, ToolResult


def create_builtin_tools() -> list[Tool]:
    """创建 Bamboo 随包提供的全部内置工具实例。"""
    from bamboo.tools.buildin.bash import BashTool
    from bamboo.tools.buildin.edit import EditTool
    from bamboo.tools.buildin.glob import GlobTool
    from bamboo.tools.buildin.grep import GrepTool
    from bamboo.tools.buildin.lsp import LSPTool
    from bamboo.tools.buildin.memory_retrieve import MemoryRetrieveTool
    from bamboo.tools.buildin.read import ReadTool
    from bamboo.tools.buildin.skill_load import SkillLoadTool
    from bamboo.tools.buildin.subagent_run import SubagentRunTool
    from bamboo.tools.buildin.task import TaskCreateTool, TaskGetTool, TaskListTool, TaskStopTool
    from bamboo.tools.buildin.todo import TodoWriteTool
    from bamboo.tools.buildin.web_fetch import WebFetchTool
    from bamboo.tools.buildin.write import WriteTool

    return [
        BashTool(),
        EditTool(),
        GlobTool(),
        GrepTool(),
        LSPTool(),
        MemoryRetrieveTool(),
        ReadTool(),
        SkillLoadTool(),
        SubagentRunTool(),
        TaskCreateTool(),
        TaskGetTool(),
        TaskListTool(),
        TaskStopTool(),
        TodoWriteTool(),
        WebFetchTool(),
        WriteTool(),
    ]

__all__ = [
    "Tool",
    "ToolResult",
    "create_builtin_tools",
]
