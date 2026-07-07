"""Tests for subagent workspace isolation."""

from __future__ import annotations

from pathlib import Path

import anyio

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.runtime.subagent_runtime import SubagentRuntime
from bamboo.runtime.subagent_workspace import SubagentWorkspaceManager
from bamboo.subagents.registry import SubagentRegistry
from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.buildin.subagent_run import SubagentRunTool
from bamboo.tools.registry import ToolRegistry


def test_writable_subagent_runs_in_tempdir_without_polluting_parent(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("old\n", encoding="utf-8")
    subagent_registry = _subagent_registry(
        tmp_path,
        "name: writer\ndescription: Write.\ntools:\n  write: true\n",
    )
    parent_context, parent_task = _parent_context(project, subagent_registry)
    workspace_root = tmp_path / "workspaces"

    class FakeAgentRuntime:
        def __init__(self, *, runtime_context, recovery_policy):
            self.runtime_context = runtime_context

        async def run(self, task):
            root = task.session.context.project_root
            (root / "app.py").write_text("new\n", encoding="utf-8")
            task.output = "changed app"
            task.status = "completed"
            return task

    monkeypatch.setattr("bamboo.runtime.agent_runtime.AgentRuntime", FakeAgentRuntime)

    async def run_test():
        return await SubagentRuntime(
            parent_context=parent_context,
            parent_task=parent_task,
            registry=subagent_registry,
            workspace_manager=SubagentWorkspaceManager(root=workspace_root),
        ).run(subagent_type="writer", description="change app", prompt="edit app")

    result = anyio.run(run_test)

    assert (project / "app.py").read_text(encoding="utf-8") == "old\n"
    assert result.workspace_mode == "tempdir"
    assert result.merge_required is True
    assert result.workspace_retained is True
    assert result.changed_files == ("app.py",)
    assert Path(result.workspace_path).is_dir()
    assert (Path(result.workspace_path) / "app.py").read_text(encoding="utf-8") == "new\n"


def test_subagent_run_tool_returns_workspace_metadata(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "file.txt").write_text("before\n", encoding="utf-8")
    subagent_registry = _subagent_registry(
        tmp_path,
        "name: writer\ndescription: Write.\ntools:\n  write: true\nworkspace_mode: tempdir\n",
    )
    parent_context, parent_task = _parent_context(project, subagent_registry)

    class FakeAgentRuntime:
        def __init__(self, *, runtime_context, recovery_policy):
            self.runtime_context = runtime_context

        async def run(self, task):
            (task.session.context.project_root / "file.txt").write_text("after\n", encoding="utf-8")
            task.output = "ok"
            task.status = "completed"
            return task

    monkeypatch.setattr("bamboo.runtime.agent_runtime.AgentRuntime", FakeAgentRuntime)
    tool = SubagentRunTool(subagent_registry=subagent_registry)
    tool.bind_runtime_context(runtime_context=parent_context, task=parent_task)

    async def run_test():
        return await tool.execute(subagent_type="writer", description="write", prompt="write")

    result = anyio.run(run_test)

    assert result.success
    assert result.metadata is not None
    assert result.metadata["workspace_mode"] == "tempdir"
    assert result.metadata["changed_files"] == ["file.txt"]
    assert result.metadata["merge_required"] is True
    assert "<workspace>" in result.content


def test_worktree_mode_falls_back_to_tempdir_for_non_git_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    subagent_registry = _subagent_registry(
        tmp_path,
        "name: writer\ndescription: Write.\ntools:\n  write: true\nworkspace_mode: worktree\n",
    )
    definition = subagent_registry.get("writer")
    assert definition is not None
    registry = ToolRegistry()
    registry.register(_NamedTool("write", risk_level="write"), source="test")

    workspace = SubagentWorkspaceManager(root=tmp_path / "workspaces").prepare(
        definition=definition,
        project_root=project,
        tool_registry=registry,
    )

    assert workspace.requested_mode == "worktree"
    assert workspace.mode == "tempdir"
    assert "fell back to tempdir" in workspace.note


def _subagent_registry(tmp_path: Path, yaml_text: str) -> SubagentRegistry:
    subagent_dir = tmp_path / "subagents"
    subagent_dir.mkdir(exist_ok=True)
    (subagent_dir / "writer.yaml").write_text(yaml_text, encoding="utf-8")
    return SubagentRegistry(subagent_dirs=[("test", subagent_dir)])


def _parent_context(project: Path, subagent_registry: SubagentRegistry):
    factory = LLMFactory.from_mapping(_model_document())
    parent_task = TaskFactory().create(RunParams(message="parent", model="test-model", project=str(project)))
    tool_registry = ToolRegistry()
    tool_registry.register(_NamedTool("write", risk_level="write"), source="test")
    parent_context = RuntimeContextBuilder(
        event_bus=EventBus(),
        llm_factory=factory,
        tool_registry=tool_registry,
        subagent_registry=subagent_registry,
        mcp_enabled=False,
    ).build(parent_task)
    return parent_context, parent_task


def _model_document() -> dict:
    return {
        "default_model": "test-model",
        "models": {
            "test-model": {
                "provider": "deepseek",
                "model": "provider-model-id",
                "api_key": "test-api-key",
                "base_url": "https://llm.test/v1",
            }
        },
    }


class _NamedTool(Tool):
    description = "named test tool"

    def __init__(self, name: str, *, risk_level: str = "read") -> None:
        self.name = name
        self.risk_level = risk_level

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(content="ok")
