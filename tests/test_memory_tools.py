"""Tests for memory maintenance tools."""

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
from bamboo.tools.buildin.memory import MemoryBackfillTool, MemoryReadTool, MemorySearchTool, MemoryUpdateTool


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_memory_update_appends_chat_knowledge_and_read_search_find_it(tmp_path: Path) -> None:
    manager = MemoryManager()
    task = _task(mode="chat", project_root=tmp_path)
    update_tool = _bind(MemoryUpdateTool(memory_manager=manager), manager=manager, task=task)
    read_tool = _bind(MemoryReadTool(memory_manager=manager), manager=manager, task=task)
    search_tool = _bind(MemorySearchTool(memory_manager=manager), manager=manager, task=task)

    async def run_test() -> None:
        updated = await update_tool.execute(
            scope="auto",
            file="preferences.md",
            operation="append",
            content="- Prefer concise Chinese answers.",
            source_ref=f"{task.session_id}/{task.task_id}",
        )
        assert updated.success
        assert updated.metadata["scope"] == "chat"  # type: ignore[index]

        read = await read_tool.execute(scope="chat", file="preferences.md")
        assert "Prefer concise Chinese answers" in read.content
        assert f"source: {task.session_id}/{task.task_id}" in read.content

        searched = await search_tool.execute(query="concise Chinese")
        assert "Prefer concise Chinese answers" in searched.content

    anyio.run(run_test)


def test_memory_update_project_current_does_not_pollute_other_project(tmp_path: Path) -> None:
    manager = MemoryManager()
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    task_a = _task(mode="project", project_root=project_a)
    task_b = _task(mode="project", project_root=project_b)
    update_tool = _bind(MemoryUpdateTool(memory_manager=manager), manager=manager, task=task_a)

    async def run_test() -> None:
        result = await update_tool.execute(
            scope="auto",
            file="decisions.md",
            operation="append",
            content=f"- Project A uses Redis. source: {task_a.session_id}/{task_a.task_id}",
        )
        assert result.success

    anyio.run(run_test)

    content_a = "\n".join(file.content for file in manager.load_knowledge_files_for_retrieval(task_a.session))
    content_b = "\n".join(file.content for file in manager.load_knowledge_files_for_retrieval(task_b.session))
    assert "Project A uses Redis" in content_a
    assert "Project A uses Redis" not in content_b


def test_memory_update_remove_matching_forgets_lines(tmp_path: Path) -> None:
    manager = MemoryManager()
    task = _task(mode="chat", project_root=tmp_path)
    tool = _bind(MemoryUpdateTool(memory_manager=manager), manager=manager, task=task)

    async def run_test() -> None:
        await tool.execute(
            file="global.md",
            operation="append",
            content=f"- Remove this temporary preference. source: {task.session_id}/{task.task_id}",
        )
        removed = await tool.execute(file="global.md", operation="remove_matching", match_text="temporary preference")
        assert removed.success
        assert removed.metadata["removed_count"] == 1  # type: ignore[index]

    anyio.run(run_test)

    assert "temporary preference" not in manager.read_knowledge(task.session, file_name="global.md")[0].content


def test_memory_backfill_appends_concise_source_refs(tmp_path: Path) -> None:
    manager = MemoryManager()
    task = _task(mode="chat", project_root=tmp_path)
    scope = manager.resolve_scope(task.session)
    store = SessionMemoryStore(memory_dir=scope.root / "2026-07-06", session_id="session-source")
    source_task = _task(
        mode="chat",
        project_root=tmp_path,
        task_id="task-source",
        session_id="session-source",
        message="remember vector database decision",
    )
    source_task.output = "The team chose sqlite source log index for local retrieval."
    source_task.status = "completed"
    source_task.session.memory_store = store
    store.append_turn(source_task)
    tool = _bind(MemoryBackfillTool(memory_manager=manager), manager=manager, task=task)

    async def run_test() -> None:
        result = await tool.execute(query="sqlite source", file="decisions.md")
        assert result.success
        assert result.metadata["source_refs"] == ["session-source/task-source"]  # type: ignore[index]

    anyio.run(run_test)

    content = manager.read_knowledge(task.session, file_name="decisions.md")[0].content
    assert "sqlite source log index" in content
    assert "source: session-source/task-source" in content
    assert len(content) < 600


def _bind(tool, *, manager: MemoryManager, task: Task):
    runtime_context = RuntimeContextBuilder(
        event_bus=_DummyEventBus(),
        llm_factory=LLMFactory.from_mapping(_model_document()),
        memory_manager=manager,
    ).build(task)
    tool.bind_runtime_context(runtime_context=runtime_context, task=task)
    return tool


def _task(
    *,
    mode: str,
    project_root: Path,
    task_id: str = "task-a",
    session_id: str = "session-a",
    message: str = "hello",
) -> Task:
    project_root.mkdir(parents=True, exist_ok=True)
    run_params = RunParams(
        message=message,
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
