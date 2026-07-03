"""Tests for memory_retrieve tool."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.memory.manager import MemoryManager
from bamboo.memory.session_store import SessionMemoryStore
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.tools.buildin.memory_retrieve import MemoryRetrieveTool


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_memory_retrieve_searches_knowledge_files(tmp_path: Path) -> None:
    manager = MemoryManager()
    task = _task(mode="project", project_root=tmp_path / "project-a")
    context = manager.load_prompt_context(task.session)
    (context.knowledge_dir / "architecture.md").write_text(
        "- Redis queue handles async jobs. source: session-a/task-a\n",
        encoding="utf-8",
    )
    tool = _bound_tool(manager=manager, task=task)

    async def run_test() -> None:
        result = await tool.execute(query="Redis queue", source="knowledge")
        assert result.success
        assert "Redis queue handles async jobs" in result.content
        assert result.metadata is not None
        assert result.metadata["matches"][0]["origin"] == "knowledge"

    anyio.run(run_test)


def test_memory_retrieve_searches_source_logs_when_requested(tmp_path: Path) -> None:
    manager = MemoryManager()
    task = _task(mode="chat", project_root=tmp_path)
    scope = manager.resolve_scope(task.session)
    store = SessionMemoryStore(memory_dir=scope.root / "2026-07-03", session_id="session-source")
    source_task = _task(mode="chat", project_root=tmp_path, task_id="task-source", session_id="session-source")
    source_task.output = "Use sqlite source log index"
    source_task.status = "completed"
    source_task.session.memory_store = store
    store.append_turn(source_task)
    tool = _bound_tool(manager=manager, task=task)

    async def run_test() -> None:
        result = await tool.execute(query="sqlite source", source="source_log")
        assert result.success
        assert "Use sqlite source log index" in result.content
        assert result.metadata is not None
        assert result.metadata["matches"][0]["origin"] == "source_log"

    anyio.run(run_test)


def _bound_tool(*, manager: MemoryManager, task: Task) -> MemoryRetrieveTool:
    runtime_context = RuntimeContextBuilder(
        event_bus=_DummyEventBus(),
        llm_factory=LLMFactory.from_mapping(_model_document()),
        memory_manager=manager,
    ).build(task)
    tool = MemoryRetrieveTool(memory_manager=manager)
    tool.bind_runtime_context(runtime_context=runtime_context, task=task)
    return tool


def _task(
    *,
    mode: str,
    project_root: Path,
    task_id: str = "task-a",
    session_id: str = "session-a",
) -> Task:
    project_root.mkdir(parents=True, exist_ok=True)
    run_params = RunParams(
        message="hello",
        model="test-model",
        project=str(project_root),
        session_mode=SessionMode.project if mode == "project" else SessionMode.chat,
        task_id=task_id,
        session_id=session_id,
    )
    session = Session(
        session_id=session_id,
        model="test-model",
        provider="deepseek",
        context=Context(
            session_id=session_id,
            project_root=project_root,
            memory_dir=Path.cwd(),
            system_prompt="system",
            metadata={"prompt_mode": mode},
        ),
        current_task_id=task_id,
    )
    session.add_message("user", run_params.message)
    session.add_message("assistant", "Use sqlite source log index", agent_name="llm:test")
    return Task(
        platform="cli",
        session_id=session_id,
        task_id=task_id,
        user_query=run_params.message,
        session=session,
        config={},
        run_params=run_params,
        memory_dir=Path.cwd(),
    )


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


class _DummyEventBus:
    def subscribe(self, *args, **kwargs):
        return lambda: None
