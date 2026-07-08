"""验证完整会话记录写入 memory dates/projects。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import anyio
import pytest

from bamboo.factory.event_bus import EventBus
from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.factory.session import SessionFactory
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.constant import TaskCreateEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.memory.get_memory_path import get_memory_dir_name
from bamboo.memory.session_store import SessionMemoryStore
from bamboo.runtime.task_runtime import TaskRuntime


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """隔离用户空间，避免写入真实 ~/.bamboo。"""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_chat_session_persists_full_messages_to_memory_dates(tmp_path: Path) -> None:
    """验证 chat 模式保存到 ~/.bamboo/memory/dates。"""
    run_params = RunParams(
        message="hello",
        project=str(tmp_path),
        session_mode=SessionMode.chat,
        task_id="task-1",
        session_id="session-1",
    )
    memory_dir = tmp_path / "home" / ".bamboo" / "memory" / "dates" / "today"
    session = SessionFactory().create(memory_dir_path=memory_dir, run_params=run_params)
    session.add_message("assistant", "hi", agent_name="llm:test")

    session_dirs = [path for path in memory_dir.iterdir() if path.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]
    assert session_dir.name != "session-1"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{6}", session_dir.name)
    assert (session_dir / "session.json").is_file()
    assert (session_dir / "system_prompt.md").is_file()
    messages = _read_jsonl(session_dir / "messages.jsonl")

    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["message_id"]
    assert messages[0]["time"]
    assert messages[0]["task_id"] == "task-1"
    assert messages[0]["content"] == "hello"


def test_project_session_persists_to_memory_projects(tmp_path: Path) -> None:
    """验证 project 模式保存到 ~/.bamboo/memory/projects。"""
    project_root = tmp_path / "demo-project"
    project_root.mkdir()
    memory_dir = tmp_path / "home" / ".bamboo" / "memory" / "projects" / get_memory_dir_name(project_root)
    run_params = RunParams(
        message="inspect project",
        project=str(project_root),
        session_mode=SessionMode.project,
        task_id="task-1",
        session_id="session-project",
    )

    SessionFactory().create(memory_dir_path=memory_dir, run_params=run_params)

    session_dirs = [path for path in memory_dir.iterdir() if path.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{6}", session_dir.name)
    session_data = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
    assert session_data["mode"] == "project"
    assert session_data["project_root"] == str(project_root)
    assert (session_dir / "messages.jsonl").is_file()


def test_compaction_persists_before_and_after_messages(tmp_path: Path) -> None:
    """验证压缩前后内容保存到 compactions.jsonl。"""
    memory_dir = tmp_path / "home" / ".bamboo" / "memory" / "dates" / "today"
    run_params = RunParams(
        message="first",
        project=str(tmp_path),
        session_mode=SessionMode.chat,
        task_id="task-compact",
        session_id="session-compact",
    )
    session = SessionFactory().create(memory_dir_path=memory_dir, run_params=run_params)
    second = session.add_message("assistant", "second", agent_name="llm:test")

    session.replace_messages_with_summary([session.messages[0], second], "short summary", agent_name="summary:test")

    session_dirs = [path for path in memory_dir.iterdir() if path.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]
    compactions = _read_jsonl(session_dir / "compactions.jsonl")
    messages = _read_jsonl(session_dir / "messages.jsonl")

    assert compactions[0]["before_messages"][0]["content"] == "first"
    assert compactions[0]["summary"] == "short summary"
    assert compactions[0]["after_active_message_ids"]
    assert messages[-1]["role"] == "system"
    assert messages[-1]["subtype"] == "compaction"
    assert messages[-1]["content"].startswith("[conversation-summary]")
    assert messages[-1]["compaction"]["before_messages"][0]["content"] == "first"
    assert messages[-1]["compaction"]["after_active_message_ids"]


def test_session_store_persists_events_and_tasks(tmp_path: Path) -> None:
    """验证 store 可写入并读取 events.jsonl / tasks.jsonl。"""
    store = SessionMemoryStore(
        memory_dir=tmp_path / "memory",
        session_id="session-trace",
    )
    store.append_event(
        TaskCreateEvent(
            session_id="session-trace",
            task_id="task-trace",
            title="trace task",
        )
    )
    task = TaskFactoryStub.task(session_id="session-trace", task_id="task-trace")
    store.append_task(task, action="created")

    events = store.load_events()
    tasks = store.load_tasks()

    assert events[0]["type"] == "task-create"
    assert events[0]["task_id"] == "task-trace"
    assert tasks[0]["action"] == "created"
    assert tasks[0]["status"] == "created"


def test_task_runtime_records_trace_events_and_task_snapshots(tmp_path: Path) -> None:
    """验证 TaskRuntime 自动记录当前任务的事件和状态快照。"""
    event_bus = EventBus()
    runtime = TaskRuntime(
        event_bus=event_bus,
        agent_factory=lambda _event_bus: _SuccessfulAgent(),
        llm_factory=LLMFactory.from_mapping(_model_document()),
    )
    run_params = RunParams(
        message="trace this task",
        project=str(tmp_path),
        session_mode=SessionMode.chat,
        task_id="task-runtime-trace",
        session_id="session-runtime-trace",
    )

    async def run_test() -> None:
        await runtime.run(run_params)

    anyio.run(run_test)

    trace_dirs = list((tmp_path / "home" / ".bamboo" / "memory").rglob("events.jsonl"))
    assert len(trace_dirs) == 1
    session_dir = trace_dirs[0].parent
    events = _read_jsonl(session_dir / "events.jsonl")
    tasks = _read_jsonl(session_dir / "tasks.jsonl")
    turns = _read_jsonl(session_dir / "turns.jsonl")

    assert [event["type"] for event in events] == [
        "task-create",
        "task-status-change",
        "step-start",
        "task-status-change",
        "step-finish",
    ]
    assert all(event["session_id"] == "session-runtime-trace" for event in events)
    assert {task["action"] for task in tasks} >= {"created", "status:running", "status:completed"}
    assert tasks[-1]["status"] == "completed"
    assert turns[0]["type"] == "turn"
    assert turns[0]["task_id"] == "task-runtime-trace"
    assert turns[0]["user_message"] == "trace this task"
    assert turns[0]["assistant_answer"] == "done"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class _SuccessfulAgent:
    async def run(self, task: Task) -> Task:
        task.output = "done"
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


class TaskFactoryStub:
    @staticmethod
    def task(*, session_id: str, task_id: str) -> Task:
        run_params = RunParams(
            message="trace task",
            session_id=session_id,
            task_id=task_id,
        )
        session = Session(
            session_id=session_id,
            model="",
            provider="",
            context=Context(
                session_id=session_id,
                project_root=Path.cwd(),
                memory_dir=Path.cwd(),
                system_prompt="",
            ),
        )
        return Task(
            platform="cli",
            session_id=session_id,
            task_id=task_id,
            user_query="trace task",
            session=session,
            config={},
            run_params=run_params,
            memory_dir=Path.cwd(),
        )
