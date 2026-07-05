"""Cron scheduler tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import anyio
import pytest

from bamboo.cron import CronJob, CronRetryPolicy, CronScheduler, CronStore, HeartbeatRunner, cron_matches
from bamboo.factory.event_bus import EventBus
from bamboo.helpers.constant import CronHeartbeatEvent, CronJobCompleteEvent, CronJobStartEvent


def test_cron_expression_matches_minute_hour_and_steps() -> None:
    now = datetime(2026, 7, 5, 9, 30, tzinfo=timezone.utc)

    assert cron_matches("30 9 * * *", now)
    assert cron_matches("*/15 9 * * *", now)
    assert not cron_matches("31 9 * * *", now)


def test_cron_store_register_enable_disable_and_log(tmp_path: Path) -> None:
    store = CronStore(root=tmp_path)
    job = CronJob(name="daily", schedule="0 9 * * *", prompt="daily report")

    store.register_job(job)
    disabled = store.set_enabled("daily", False)
    enabled = store.set_enabled("daily", True)

    assert disabled.enabled is False
    assert enabled.enabled is True
    assert store.load_jobs()[0].name == "daily"


def test_scheduler_tick_runs_due_job_once_per_minute(tmp_path: Path) -> None:
    store = CronStore(root=tmp_path)
    store.register_job(CronJob(name="every-minute", schedule="* * * * *", prompt="run me"))
    runtime = _RecordingRuntime()
    scheduler = CronScheduler(store=store, runtime_factory=lambda: runtime)
    now = datetime(2026, 7, 5, 9, 30, 12, tzinfo=timezone.utc)

    async def run_test() -> None:
        first = await scheduler.tick(now)
        second = await scheduler.tick(now)
        assert len(first) == 1
        assert second == []

    anyio.run(run_test)

    assert [params.message for params in runtime.run_params] == ["run me"]
    assert store.load_runs()[0]["status"] == "completed"


def test_scheduler_retries_failed_job_and_emits_events(tmp_path: Path) -> None:
    store = CronStore(root=tmp_path)
    store.register_job(
        CronJob(
            name="retry-me",
            schedule="* * * * *",
            prompt="unstable",
            retry=CronRetryPolicy(max_attempts=2, backoff="none"),
        )
    )
    event_bus = EventBus()
    emitted: list[object] = []
    event_bus.subscribe(emitted.append)
    runtime = _FailOnceRuntime()
    scheduler = CronScheduler(
        store=store,
        event_bus=event_bus,
        runtime_factory=lambda: runtime,
        sleep_fn=_no_sleep,
    )

    async def run_test() -> None:
        records = await scheduler.tick(datetime(2026, 7, 5, 9, 30, tzinfo=timezone.utc))
        assert records[0].status == "completed"
        assert records[0].attempt == 2

    anyio.run(run_test)

    assert runtime.calls == 2
    assert sum(isinstance(event, CronJobStartEvent) for event in emitted) == 2
    assert any(isinstance(event, CronJobCompleteEvent) and event.status == "failed" for event in emitted)
    assert any(isinstance(event, CronJobCompleteEvent) and event.status == "completed" for event in emitted)
    assert [record["status"] for record in store.load_runs()] == ["failed", "completed"]


def test_heartbeat_emits_due_jobs_and_drives_scheduler(tmp_path: Path) -> None:
    store = CronStore(root=tmp_path)
    store.register_job(CronJob(name="heartbeat-job", schedule="* * * * *", prompt="heartbeat task"))
    event_bus = EventBus()
    emitted: list[object] = []
    event_bus.subscribe(emitted.append)
    runtime = _RecordingRuntime()
    scheduler = CronScheduler(store=store, event_bus=event_bus, runtime_factory=lambda: runtime)
    heartbeat = HeartbeatRunner(scheduler=scheduler, event_bus=event_bus)

    async def run_test() -> None:
        records = await heartbeat.run_once(datetime(2026, 7, 5, 9, 30, tzinfo=timezone.utc))
        assert len(records) == 1

    anyio.run(run_test)

    heartbeat_events = [event for event in emitted if isinstance(event, CronHeartbeatEvent)]
    assert heartbeat_events[0].due_jobs == ["heartbeat-job"]
    assert runtime.run_params[0].platform == "cron"


async def _no_sleep(_seconds: float) -> None:
    return None


class _RecordingRuntime:
    def __init__(self) -> None:
        self.run_params = []

    async def run(self, run_params):
        self.run_params.append(run_params)
        return object()


class _FailOnceRuntime:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, run_params):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        return object()
