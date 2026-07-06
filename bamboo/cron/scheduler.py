"""Cron scheduler and heartbeat loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bamboo.cron.models import CronDeliveryMode, CronJob, CronRunRecord, HeartbeatConfig, ScheduledRun
from bamboo.cron.store import CronStore, utc_now_iso
from bamboo.factory.event_bus import EventBus, get_event_bus
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import CronHeartbeatEvent, CronJobCompleteEvent, CronJobStartEvent, SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.memory.session_store import find_latest_session_record, find_session_record, load_session_record
from bamboo.runtime import TaskRuntime

RuntimeFactory = Callable[[], TaskRuntime]
SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class CronExecution:
    """Resolved execution target for one cron attempt."""

    delivery: CronDeliveryMode
    run_params: RunParams
    task: Task | None = None
    target_record_dir: Path | None = None
    target_session_id: str = ""


class CronScheduler:
    """Select due cron jobs and execute them through TaskRuntime."""

    def __init__(
        self,
        *,
        store: CronStore | None = None,
        event_bus: EventBus | None = None,
        runtime_factory: RuntimeFactory | None = None,
        sleep_fn: SleepFn | None = None,
    ) -> None:
        self.store = store or CronStore()
        self.event_bus = event_bus or get_event_bus()
        self.runtime_factory = runtime_factory or (lambda: TaskRuntime(event_bus=self.event_bus))
        self.sleep_fn = sleep_fn or asyncio.sleep

    def due_runs(self, now: datetime | None = None) -> list[ScheduledRun]:
        """Return jobs due at the given minute and not already selected."""
        current = _normalize_minute(now or datetime.now(timezone.utc))
        due: list[ScheduledRun] = []
        for job in self.store.load_jobs():
            if not job.enabled:
                continue
            if not cron_matches(job.schedule, current):
                continue
            due_key = f"{current.isoformat()}::{job.name}"
            if self.store.last_due_key(job.name) == due_key:
                continue
            due.append(ScheduledRun(job=job, due_at=current, due_key=due_key))
        return due

    async def tick(self, now: datetime | None = None) -> list[CronRunRecord]:
        """Run all due jobs once."""
        records: list[CronRunRecord] = []
        for scheduled in self.due_runs(now):
            self.store.save_last_due_key(scheduled.job.name, scheduled.due_key)
            records.append(await self._run_job_with_retry(scheduled.job))
        return records

    async def run_forever(self, *, heartbeat: HeartbeatConfig | None = None) -> None:
        """Run heartbeat ticks until cancelled."""
        heartbeat = heartbeat or HeartbeatConfig()
        runner = HeartbeatRunner(scheduler=self, event_bus=self.event_bus, config=heartbeat)
        await runner.run_forever()

    async def _run_job_with_retry(self, job: CronJob) -> CronRunRecord:
        last_record: CronRunRecord | None = None
        for attempt in range(1, job.retry.max_attempts + 1):
            last_record = await self._run_job_once(job, attempt)
            if last_record.status == "completed":
                return last_record
            if attempt < job.retry.max_attempts:
                await self.sleep_fn(_retry_delay(job, attempt))
        assert last_record is not None
        return last_record

    async def _run_job_once(self, job: CronJob, attempt: int) -> CronRunRecord:
        run_id = str(uuid4())
        started_at = utc_now_iso()
        status = "completed"
        error = ""
        execution: CronExecution | None = None
        try:
            runtime = self.runtime_factory()
            execution = _execution_for_job(job, runtime)
        except Exception as exc:
            status = "failed"
            error = str(exc)
            execution = _failed_execution_for_job(job)
        run_params = execution.run_params
        start_event = CronJobStartEvent(
            session_id=run_params.session_id,
            task_id=run_params.task_id,
            job_name=job.name,
            run_id=run_id,
            attempt=attempt,
            delivery=execution.delivery,
            target_session_id=execution.target_session_id,
            target_record_dir=str(execution.target_record_dir or ""),
        )
        await self.event_bus.emit(start_event)
        _append_cron_event(execution, start_event)
        if not error:
            try:
                if execution.task is not None:
                    await runtime.run_existing_task(execution.task)
                else:
                    await runtime.run(run_params)
            except Exception as exc:
                status = "failed"
                error = str(exc)
        finished_at = utc_now_iso()
        record = CronRunRecord(
            run_id=run_id,
            job_name=job.name,
            task_id=run_params.task_id,
            session_id=run_params.session_id,
            delivery=execution.delivery,
            target_session_id=execution.target_session_id,
            target_record_dir=str(execution.target_record_dir or ""),
            status=status,
            attempt=attempt,
            started_at=started_at,
            finished_at=finished_at,
            error=error,
        )
        self.store.append_run(record)
        complete_event = CronJobCompleteEvent(
            session_id=run_params.session_id,
            task_id=run_params.task_id,
            job_name=job.name,
            run_id=run_id,
            status=status,
            attempt=attempt,
            error=error,
            delivery=execution.delivery,
            target_session_id=execution.target_session_id,
            target_record_dir=str(execution.target_record_dir or ""),
        )
        await self.event_bus.emit(complete_event)
        _append_cron_event(execution, complete_event)
        return record


class HeartbeatRunner:
    """Periodic heartbeat that drives cron ticks."""

    def __init__(
        self,
        *,
        scheduler: CronScheduler,
        event_bus: EventBus | None = None,
        config: HeartbeatConfig | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.event_bus = event_bus or get_event_bus()
        self.config = config or HeartbeatConfig()
        self.tick_count = 0

    async def run_once(self, now: datetime | None = None) -> list[CronRunRecord]:
        """Emit one heartbeat and run one scheduler tick."""
        self.tick_count += 1
        due = self.scheduler.due_runs(now)
        await self.event_bus.emit(
            CronHeartbeatEvent(
                session_id="cron",
                task_id="cron-heartbeat",
                tick=self.tick_count,
                due_jobs=[scheduled.job.name for scheduled in due],
            )
        )
        records: list[CronRunRecord] = []
        for scheduled in due:
            self.scheduler.store.save_last_due_key(scheduled.job.name, scheduled.due_key)
            records.append(await self.scheduler._run_job_with_retry(scheduled.job))
        return records

    async def run_forever(self) -> None:
        """Run heartbeat loop until cancelled."""
        while self.config.enabled:
            await self.run_once()
            await self.scheduler.sleep_fn(self.config.interval_seconds)


def cron_matches(expression: str, value: datetime) -> bool:
    """Return whether a five-field cron expression matches a datetime."""
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("cron schedule must have five fields: minute hour day month weekday")
    minute, hour, day, month, weekday = fields
    return (
        _field_matches(minute, value.minute, 0, 59)
        and _field_matches(hour, value.hour, 0, 23)
        and _field_matches(day, value.day, 1, 31)
        and _field_matches(month, value.month, 1, 12)
        and _field_matches(weekday, (value.weekday() + 1) % 7, 0, 6)
    )


def _field_matches(field: str, value: int, minimum: int, maximum: int) -> bool:
    for part in field.split(","):
        if _part_matches(part.strip(), value, minimum, maximum):
            return True
    return False


def _part_matches(part: str, value: int, minimum: int, maximum: int) -> bool:
    if part == "*":
        return True
    if part.startswith("*/"):
        step = int(part[2:])
        if step <= 0:
            raise ValueError("cron step must be positive")
        return (value - minimum) % step == 0
    if "-" in part:
        start_raw, end_raw = part.split("-", 1)
        start = int(start_raw)
        end = int(end_raw)
        if start > end:
            raise ValueError("cron range start must be <= end")
        return start <= value <= end
    number = int(part)
    if number < minimum or number > maximum:
        raise ValueError(f"cron value out of range: {number}")
    return number == value


def _normalize_minute(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0)


def _execution_for_job(job: CronJob, runtime: TaskRuntime) -> CronExecution:
    delivery = _delivery_for_job(job)
    if delivery == "main":
        return _main_execution_for_job(job, runtime)
    return CronExecution(delivery="isolated", run_params=_run_params_for_job(job, delivery="isolated"))


def _main_execution_for_job(job: CronJob, runtime: TaskRuntime) -> CronExecution:
    project = Path(job.project).expanduser() if job.project else None
    mode = "project" if project is not None else "auto"
    record_dir = _target_record_dir_for_job(job, mode=mode, project=project)
    if record_dir is None:
        target = job.session_id or "latest"
        raise ValueError(f"cron main delivery target session not found: {target}")
    session = load_session_record(record_dir)
    run_params = _run_params_for_job(
        job,
        delivery="main",
        session_id=session.session_id,
        project=str(session.context.project_root),
        session_mode=SessionMode.project if session.context.metadata.get("prompt_mode") == "project" else SessionMode.chat,
    )
    if job.model:
        run_params.model = job.model
    else:
        run_params.model = session.model
    if job.provider:
        run_params.provider = job.provider
    else:
        run_params.provider = session.provider
    previous = Task(
        platform="cron",
        session_id=session.session_id,
        task_id=run_params.task_id,
        user_query="",
        session=session,
        config=runtime.task_factory.config,
        run_params=run_params,
        memory_dir=session.memory_store.memory_dir if session.memory_store else record_dir.parent,
    )
    task = runtime.create_followup_task(previous, job.prompt)
    return CronExecution(
        delivery="main",
        run_params=task.run_params,
        task=task,
        target_record_dir=record_dir,
        target_session_id=session.session_id,
    )


def _target_record_dir_for_job(job: CronJob, *, mode: str, project: Path | None) -> Path | None:
    if job.record_dir:
        candidate = Path(job.record_dir).expanduser()
        if job.session_id:
            return find_session_record(job.session_id, mode=mode, project_path=project, record_dir=candidate)
        return candidate if (candidate / "session.json").is_file() else None
    if job.session_id:
        return find_session_record(job.session_id, mode=mode, project_path=project)
    latest = find_latest_session_record(mode=mode, project_path=project)
    return latest.record_dir if latest is not None else None


def _failed_execution_for_job(job: CronJob) -> CronExecution:
    delivery = _delivery_for_job(job)
    return CronExecution(
        delivery=delivery,
        run_params=_run_params_for_job(
            job,
            delivery=delivery,
            session_id=job.session_id or "cron",
        ),
        target_session_id=job.session_id,
        target_record_dir=Path(job.record_dir).expanduser() if job.record_dir else None,
    )


def _run_params_for_job(
    job: CronJob,
    *,
    delivery: CronDeliveryMode,
    session_id: str | None = None,
    project: str | None = None,
    session_mode: SessionMode | None = None,
    ) -> RunParams:
    resolved_session_id = session_id or (str(uuid4()) if delivery == "isolated" else (job.session_id or "cron"))
    resolved_project = project or job.project or str(Path.cwd())
    return RunParams(
        platform="cron",
        message=job.prompt,
        project=resolved_project,
        model=job.model,
        provider=job.provider,
        permission=job.permission,
        no_stream=job.no_stream,
        yes_all=job.yes_all,
        debug_events=job.debug_events,
        session_mode=session_mode or (SessionMode.project if job.project else SessionMode.chat),
        task_id=str(uuid4()),
        session_id=resolved_session_id,
    )


def _delivery_for_job(job: CronJob) -> CronDeliveryMode:
    return job.delivery or job.session


def _append_cron_event(execution: CronExecution, event: CronJobStartEvent | CronJobCompleteEvent) -> None:
    if execution.delivery != "main" or execution.target_record_dir is None:
        return
    try:
        session = load_session_record(execution.target_record_dir)
        if session.memory_store is not None:
            session.memory_store.append_event(event)
    except Exception:
        return


def _retry_delay(job: CronJob, attempt: int) -> float:
    if job.retry.backoff == "none":
        return 0.0
    if job.retry.backoff == "linear":
        return min(job.retry.initial_delay_seconds * attempt, job.retry.max_delay_seconds)
    return min(job.retry.initial_delay_seconds * (2 ** (attempt - 1)), job.retry.max_delay_seconds)
