"""Cron main session delivery tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import anyio
import pytest

from bamboo.cron import CronJob, CronScheduler, CronStore
from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import CronJobCompleteEvent, CronJobStartEvent, SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.memory.get_memory_path import get_date_memory_path
from bamboo.memory.session_store import SessionMemoryStore


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    return home_dir


def test_cron_main_delivery_appends_followup_to_target_session(tmp_path: Path) -> None:
    store = CronStore(root=tmp_path / "bamboo")
    record_dir = _create_chat_record(session_id="main-session")
    store.register_job(
        CronJob(
            name="main-job",
            schedule="* * * * *",
            prompt="daily summary",
            session="main",
            delivery="main",
            session_id="main-session",
        )
    )
    runtime = _RecordingRuntime()
    emitted: list[object] = []
    scheduler = CronScheduler(store=store, event_bus=_EventBus(emitted), runtime_factory=lambda: runtime)

    async def run_test() -> None:
        records = await scheduler.tick(datetime(2026, 7, 6, 9, 30, tzinfo=timezone.utc))
        assert records[0].status == "completed"
        assert records[0].session_id == "main-session"
        assert records[0].delivery == "main"
        assert records[0].target_record_dir == str(record_dir)

    anyio.run(run_test)

    assert runtime.existing_tasks[0].session_id == "main-session"
    assert runtime.existing_tasks[0].user_query == "daily summary"
    persisted = SessionMemoryStore(memory_dir=record_dir.parent, session_id="main-session", record_dir=record_dir)
    event_types = [event["type"] for event in persisted.load_events()]
    assert "cron-job-start" in event_types
    assert "cron-job-complete" in event_types
    assert any(isinstance(event, CronJobStartEvent) and event.session_id == "main-session" for event in emitted)
    assert any(isinstance(event, CronJobCompleteEvent) and event.session_id == "main-session" for event in emitted)


def test_cron_isolated_delivery_does_not_append_to_latest_session(tmp_path: Path) -> None:
    store = CronStore(root=tmp_path / "bamboo")
    record_dir = _create_chat_record(session_id="main-session")
    store.register_job(CronJob(name="isolated-job", schedule="* * * * *", prompt="isolated"))
    runtime = _RecordingRuntime()
    scheduler = CronScheduler(store=store, runtime_factory=lambda: runtime)

    async def run_test() -> None:
        records = await scheduler.tick(datetime(2026, 7, 6, 9, 31, tzinfo=timezone.utc))
        assert records[0].status == "completed"
        assert records[0].delivery == "isolated"
        assert records[0].session_id != "main-session"

    anyio.run(run_test)

    persisted = SessionMemoryStore(memory_dir=record_dir.parent, session_id="main-session", record_dir=record_dir)
    assert [event["type"] for event in persisted.load_events()] == []
    assert runtime.run_params[0].message == "isolated"


def test_cron_main_delivery_uses_latest_session_when_target_not_set(tmp_path: Path) -> None:
    store = CronStore(root=tmp_path / "bamboo")
    _create_chat_record(session_id="older", updated_at="2026-07-06T00:00:00+00:00")
    latest = _create_chat_record(session_id="newer", updated_at="2026-07-06T01:00:00+00:00")
    store.register_job(CronJob(name="latest-job", schedule="* * * * *", prompt="latest", session="main", delivery="main"))
    runtime = _RecordingRuntime()
    scheduler = CronScheduler(store=store, runtime_factory=lambda: runtime)

    async def run_test() -> None:
        records = await scheduler.tick(datetime(2026, 7, 6, 9, 32, tzinfo=timezone.utc))
        assert records[0].session_id == "newer"
        assert records[0].target_record_dir == str(latest)

    anyio.run(run_test)

    assert runtime.existing_tasks[0].session_id == "newer"


def test_cron_main_delivery_missing_target_records_failed_run(tmp_path: Path) -> None:
    store = CronStore(root=tmp_path / "bamboo")
    store.register_job(
        CronJob(
            name="missing-main",
            schedule="* * * * *",
            prompt="x",
            session="main",
            delivery="main",
            session_id="missing",
        )
    )
    runtime = _RecordingRuntime()
    scheduler = CronScheduler(store=store, runtime_factory=lambda: runtime)

    async def run_test() -> None:
        records = await scheduler.tick(datetime(2026, 7, 6, 9, 33, tzinfo=timezone.utc))
        assert records[0].status == "failed"
        assert records[0].session_id == "missing"
        assert "target session not found" in records[0].error

    anyio.run(run_test)

    assert runtime.run_params == []
    assert runtime.existing_tasks == []
    assert store.load_runs()[0]["status"] == "failed"


def _create_chat_record(*, session_id: str, updated_at: str = "2026-07-06T00:00:00+00:00") -> Path:
    memory_dir = get_date_memory_path()
    record_dir = memory_dir / session_id
    store = SessionMemoryStore(memory_dir=memory_dir, session_id=session_id, record_dir=record_dir)
    store.save_session(
        mode="chat",
        project_root=Path.cwd(),
        model="test-model",
        provider="deepseek",
        system_prompt="system",
        metadata={"prompt_mode": "chat"},
    )
    session_json = record_dir / "session.json"
    payload = session_json.read_text(encoding="utf-8")
    payload = payload.replace('"updated_at": "' + store.load_session()["updated_at"] + '"', f'"updated_at": "{updated_at}"')
    session_json.write_text(payload, encoding="utf-8")
    return record_dir


class _RecordingRuntime:
    def __init__(self) -> None:
        self.run_params = []
        self.existing_tasks = []
        self.task_factory = _TaskFactory()

    async def run(self, run_params):
        self.run_params.append(run_params)
        return object()

    async def run_existing_task(self, task):
        self.existing_tasks.append(task)
        task.output = "ok"
        task.status = "completed"
        return task

    def create_followup_task(self, previous_task: Task, message: str) -> Task:
        previous_task.session.add_message("user", message)
        run_params = RunParams(
            platform="cron",
            message=message,
            project=str(previous_task.session.context.project_root),
            session_mode=SessionMode.chat,
            task_id="cron-task",
            session_id=previous_task.session_id,
        )
        return Task(
            platform="cron",
            session_id=previous_task.session_id,
            task_id="cron-task",
            user_query=message,
            session=previous_task.session,
            config=previous_task.config,
            run_params=run_params,
            memory_dir=previous_task.memory_dir,
        )


class _TaskFactory:
    config = {}


class _EventBus:
    def __init__(self, emitted: list[object]) -> None:
        self.emitted = emitted

    async def emit(self, event: object) -> None:
        self.emitted.append(event)
