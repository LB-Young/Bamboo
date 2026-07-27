"""Built-in tools for Bamboo."""

from bamboo.tools.buildin.base import Tool, ToolResult


def create_builtin_tools() -> list[Tool]:
    """创建 Bamboo 随包提供的全部内置工具实例。"""
    from bamboo.tools.buildin.bash import BashTool
    from bamboo.tools.buildin.bkn_action_execute import BKNActionExecuteTool
    from bamboo.tools.buildin.bkn_action_prepare import BKNActionPrepareTool
    from bamboo.tools.buildin.bkn_export import BKNExportTool
    from bamboo.tools.buildin.bkn_ingest import BKNIngestTool
    from bamboo.tools.buildin.bkn_ingest_submit import BKNIngestSubmitTool
    from bamboo.tools.buildin.bkn_list_actions import BKNListActionsTool
    from bamboo.tools.buildin.bkn_retrieval import BKNRetrievalTool
    from bamboo.tools.buildin.bkn_update_manifest import BKNUpdateManifestTool
    from bamboo.tools.buildin.bkn_update_topology import BKNUpdateTopologyTool
    from bamboo.tools.buildin.browser import BrowserTool
    from bamboo.tools.buildin.cron import (
        CronAddTool,
        CronDisableTool,
        CronEnableTool,
        CronGetTool,
        CronListTool,
        CronRunsTool,
        CronTickTool,
    )
    from bamboo.tools.buildin.edit import EditTool
    from bamboo.tools.buildin.glob import GlobTool
    from bamboo.tools.buildin.grep import GrepTool
    from bamboo.tools.buildin.lsp import LSPTool
    from bamboo.tools.buildin.media_generation import ImageEditTool, TextToImageTool, TextToVideoTool
    from bamboo.tools.buildin.memory import MemoryBackfillTool, MemoryReadTool, MemorySearchTool, MemoryUpdateTool
    from bamboo.tools.buildin.memory_retrieve import MemoryRetrieveTool
    from bamboo.tools.buildin.package_install import SkillInstallTool, WorkflowInstallTool
    from bamboo.tools.buildin.read import ReadTool
    from bamboo.tools.buildin.skill_load import SkillLoadTool
    from bamboo.tools.buildin.subagent_run import SubagentRunTool
    from bamboo.tools.buildin.task import TaskCreateTool, TaskGetTool, TaskListTool, TaskStopTool
    from bamboo.tools.buildin.todo import TodoWriteTool
    from bamboo.tools.buildin.web_fetch import WebFetchTool
    from bamboo.tools.buildin.workflow import WorkflowLoadTool, WorkflowRunTool
    from bamboo.tools.buildin.write import WriteTool

    return [
        BashTool(),
        BKNActionExecuteTool(),
        BKNActionPrepareTool(),
        BKNExportTool(),
        BKNIngestSubmitTool(),
        BKNIngestTool(),
        BKNListActionsTool(),
        BKNRetrievalTool(),
        BKNUpdateManifestTool(),
        BKNUpdateTopologyTool(),
        BrowserTool(),
        CronAddTool(),
        CronDisableTool(),
        CronEnableTool(),
        CronGetTool(),
        CronListTool(),
        CronRunsTool(),
        CronTickTool(),
        EditTool(),
        GlobTool(),
        GrepTool(),
        LSPTool(),
        ImageEditTool(),
        MemoryBackfillTool(),
        MemoryReadTool(),
        MemoryRetrieveTool(),
        MemorySearchTool(),
        MemoryUpdateTool(),
        ReadTool(),
        SkillInstallTool(),
        SkillLoadTool(),
        SubagentRunTool(),
        TaskCreateTool(),
        TaskGetTool(),
        TaskListTool(),
        TaskStopTool(),
        TextToImageTool(),
        TextToVideoTool(),
        TodoWriteTool(),
        WebFetchTool(),
        WorkflowInstallTool(),
        WorkflowLoadTool(),
        WorkflowRunTool(),
        WriteTool(),
    ]

__all__ = [
    "Tool",
    "ToolResult",
    "create_builtin_tools",
]
