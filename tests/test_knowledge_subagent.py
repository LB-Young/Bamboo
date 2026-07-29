"""Tests for post-task knowledge curation."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace

import anyio

from bamboo.factory.context import Context
from bamboo.factory.event_bus import EventBus
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import KnowledgeUpdateErrorEvent, KnowledgeUpdateEvent, SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.memory.knowledge_subagent import KnowledgeSubagent
from bamboo.memory.manager import MemoryManager
from bamboo.memory.session_store import SessionMemoryStore
from bamboo.runtime.task_runtime import TaskRuntime


def test_knowledge_subagent_appends_project_current_update(tmp_path: Path) -> None:
    manager = MemoryManager(memory_root=tmp_path / "memory")
    task = _task(tmp_path=tmp_path, mode="project")
    task.session.memory_store = SessionMemoryStore(memory_dir=tmp_path / "memory" / "projects", session_id=task.session_id)
    task.session.memory_store.append_turn(task)
    event_bus = EventBus()
    events: list[object] = []
    event_bus.subscribe(events.append)

    async def runner(_prompt: str) -> str:
        return (
            '{"updates":[{"scope":"project-current","file":"decisions.md","operation":"append",'
            f'"content":"- Use pytest before final answers. source: {task.session_id}/{task.task_id}"'
            '}],"skip_reason":""}'
        )

    async def run_test() -> None:
        result = await KnowledgeSubagent(
            runtime_context=SimpleNamespace(memory_manager=manager, event_bus=event_bus),
            runner=runner,
        ).maybe_update(task)
        assert result.applied == 1
        assert result.rejected == 0

    anyio.run(run_test)

    target = manager.load_prompt_context(task.session).knowledge_dir / "decisions.md"
    assert "Use pytest before final answers" in target.read_text(encoding="utf-8")
    assert any(isinstance(event, KnowledgeUpdateEvent) for event in events)


def test_knowledge_subagent_rejects_unsafe_updates(tmp_path: Path) -> None:
    manager = MemoryManager(memory_root=tmp_path / "memory")
    task = _task(tmp_path=tmp_path, mode="project")
    event_bus = EventBus()
    events: list[object] = []
    event_bus.subscribe(events.append)

    async def runner(_prompt: str) -> str:
        return (
            '{"updates":['
            '{"scope":"project-current","file":"../secrets.md","operation":"append","content":"- bad source: '
            f'{task.session_id}/{task.task_id}"}},'
            '{"scope":"project-current","file":"decisions.md","operation":"append","content":"- missing source"}'
            '],"skip_reason":""}'
        )

    async def run_test() -> None:
        result = await KnowledgeSubagent(
            runtime_context=SimpleNamespace(memory_manager=manager, event_bus=event_bus),
            runner=runner,
        ).maybe_update(task)
        assert result.applied == 0
        assert result.rejected == 2

    anyio.run(run_test)

    assert not (tmp_path / "memory" / "projects" / ".." / "secrets.md").exists()
    assert sum(isinstance(event, KnowledgeUpdateErrorEvent) for event in events) == 2


def test_task_runtime_triggers_knowledge_subagent_when_enabled(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    called = Event()

    class FakeKnowledgeSubagent:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def maybe_update(self, task: Task):
            calls.append(task.task_id)
            called.set()

    monkeypatch.setattr("bamboo.runtime.task_runtime.KnowledgeSubagent", FakeKnowledgeSubagent)
    runtime = TaskRuntime(
        event_bus=EventBus(),
        agent_factory=lambda _event_bus: _SuccessfulAgent(),
        llm_factory=LLMFactory.from_mapping(_model_document()),
        task_factory=_TaskFactoryWithMemoryConfig(),
    )

    async def run_test() -> None:
        task = await runtime.run(
            RunParams(
                message="remember this",
                project=str(tmp_path),
                session_mode=SessionMode.chat,
                task_id="task-knowledge",
                session_id="session-knowledge",
            )
        )
        assert task.status == "completed"

    anyio.run(run_test)

    assert called.wait(timeout=1)
    assert calls == ["task-knowledge"]


def test_task_runtime_does_not_block_on_knowledge_subagent(monkeypatch, tmp_path: Path) -> None:
    started = Event()
    release = Event()

    class SlowKnowledgeSubagent:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def maybe_update(self, task: Task):
            started.set()
            await anyio.to_thread.run_sync(release.wait)

    monkeypatch.setattr("bamboo.runtime.task_runtime.KnowledgeSubagent", SlowKnowledgeSubagent)
    runtime = TaskRuntime(
        event_bus=EventBus(),
        agent_factory=lambda _event_bus: _SuccessfulAgent(),
        llm_factory=LLMFactory.from_mapping(_model_document()),
        task_factory=_TaskFactoryWithMemoryConfig(),
    )

    async def run_test() -> None:
        with anyio.fail_after(0.5):
            task = await runtime.run(
                RunParams(
                    message="remember this",
                    project=str(tmp_path),
                    session_mode=SessionMode.chat,
                    task_id="task-knowledge-nonblocking",
                    session_id="session-knowledge-nonblocking",
                )
            )
        assert task.status == "completed"

    try:
        anyio.run(run_test)
        assert started.wait(timeout=1)
    finally:
        release.set()


def _task(*, tmp_path: Path, mode: str) -> Task:
    task_id = "task-a"
    session_id = "session-a"
    project_root = tmp_path / "project-a"
    project_root.mkdir(parents=True, exist_ok=True)
    run_params = RunParams(
        message="Use pytest before final answers",
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
            memory_dir=tmp_path / "memory",
            system_prompt="system",
            metadata={"prompt_mode": mode},
        ),
        current_task_id=task_id,
    )
    session.add_message("user", run_params.message)
    session.add_message("assistant", "Use pytest before final answers.", agent_name="llm:test")
    return Task(
        platform="cli",
        session_id=session_id,
        task_id=task_id,
        user_query=run_params.message,
        session=session,
        config={},
        run_params=run_params,
        memory_dir=tmp_path / "memory",
        status="completed",
        output="Use pytest before final answers.",
    )


class _SuccessfulAgent:
    async def run(self, task: Task) -> Task:
        task.output = "done"
        return task


class _TaskFactoryWithMemoryConfig:
    config = {
        "memory": {
            "knowledge_subagent": {
                "enabled": True,
                "subagent": "knowledge-curator",
            }
        }
    }

    def create(self, run_params: RunParams) -> Task:
        task = _task(tmp_path=Path(run_params.project), mode=run_params.session_mode_value)
        task.task_id = run_params.task_id
        task.session_id = run_params.session_id
        task.session.session_id = run_params.session_id
        task.session.current_task_id = run_params.task_id
        task.config = self.config
        task.run_params = run_params
        return task


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
