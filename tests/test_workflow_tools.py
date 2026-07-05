"""Workflow registry and tools tests."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.tools.buildin.workflow import WorkflowLoadTool, WorkflowRunTool
from bamboo.tools.registry import create_tool_registry
from bamboo.workflows import WorkflowRegistry, load_workflow_definition


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_load_workflow_definition_reads_entry_doc_and_run_spec(tmp_path: Path) -> None:
    workflow_dir = _workflow_dir(tmp_path, "demo")
    (workflow_dir / "WORKFLOW.md").write_text(
        """---
name: demo
description: Demo workflow.
usage: Call workflow_run.
dependencies:
  - bash
run:
  script: scripts/demo.sh
  cwd: .
  timeout: 20
  risk: read
---
# Demo Workflow

## 场景
用于测试。
""",
        encoding="utf-8",
    )

    workflow = load_workflow_definition(workflow_dir / "WORKFLOW.md", source="test")

    assert workflow.name == "demo"
    assert workflow.dependencies == ["bash"]
    assert workflow.run.script == "scripts/demo.sh"
    assert workflow.run.timeout == 20
    assert workflow.body.startswith("# Demo Workflow")


def test_workflow_registry_loads_user_workflow(tmp_path: Path) -> None:
    user_workflows = tmp_path / "workflows"
    workflow_dir = _workflow_dir(user_workflows, "user-flow")
    (workflow_dir / "WORKFLOW.md").write_text(
        """---
name: user-flow
run:
  command: "printf hello"
---
# User Flow
""",
        encoding="utf-8",
    )

    registry = WorkflowRegistry(workflow_dirs=[("user", user_workflows)])
    assert registry.available_names() == ["user-flow"]
    assert registry.get("user-flow").run.command == "printf hello"


def test_workflow_load_tool_returns_entry_document(tmp_path: Path) -> None:
    workflow_dir = _workflow_dir(tmp_path, "loadable")
    (workflow_dir / "WORKFLOW.md").write_text(
        """---
name: loadable
description: Loadable workflow.
run:
  command: "printf ok"
---
# Loadable

Use workflow_run after reading this.
""",
        encoding="utf-8",
    )
    tool = WorkflowLoadTool(workflow_registry=WorkflowRegistry(workflow_dirs=[("test", tmp_path)]))

    async def run_test() -> None:
        result = await tool.execute("loadable")
        assert result.success is True
        assert "Workflow: loadable" in result.content
        assert "Use workflow_run" in result.content

    anyio.run(run_test)


def test_workflow_run_tool_executes_declared_script(tmp_path: Path) -> None:
    workflow_dir = _workflow_dir(tmp_path, "script-flow")
    scripts_dir = workflow_dir / "scripts"
    scripts_dir.mkdir()
    script = scripts_dir / "echo.sh"
    script.write_text("printf 'workflow:%s' \"$1\"\n", encoding="utf-8")
    (workflow_dir / "WORKFLOW.md").write_text(
        """---
name: script-flow
run:
  script: scripts/echo.sh
  cwd: .
  timeout: 20
  risk: read
---
# Script Flow
""",
        encoding="utf-8",
    )
    event_bus = EventBus()
    events: list[object] = []
    event_bus.subscribe(events.append, patterns="workflow.*")
    task = TaskFactory().create(RunParams(message="run workflow", yes_all=True))
    runtime_context = RuntimeContextBuilder(
        event_bus=event_bus,
        llm_factory=LLMFactory.from_mapping(_model_document()),
    ).build(task)
    tool = WorkflowRunTool(workflow_registry=WorkflowRegistry(workflow_dirs=[("test", tmp_path)]))
    tool.bind_runtime_context(runtime_context=runtime_context, task=task)

    async def run_test() -> None:
        result = await tool.execute("script-flow", arguments="demo")
        assert result.success is True
        assert "workflow:demo" in result.content
        assert result.metadata["workflow_name"] == "script-flow"

    anyio.run(run_test)
    assert [event.type for event in events] == ["workflow-run-start", "workflow-run-complete"]


def test_builtin_tool_registry_exposes_workflow_tools() -> None:
    registry = create_tool_registry()
    assert registry.get("workflow_load") is not None
    assert registry.get("workflow_run") is not None


def _workflow_dir(root: Path, name: str) -> Path:
    workflow_dir = root / name
    workflow_dir.mkdir(parents=True, exist_ok=True)
    return workflow_dir


def _model_document() -> dict:
    return {
        "default_model": "workflow-model",
        "models": {
            "workflow-model": {
                "provider": "deepseek",
                "model": "provider-model-id",
                "api_key": "test-api-key",
                "base_url": "https://llm.test/v1",
                "max_tokens": 128,
            }
        },
    }

