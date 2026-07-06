"""Cron job models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


CronSessionMode = Literal["isolated", "main"]
CronDeliveryMode = Literal["isolated", "main"]
CronBackoffMode = Literal["none", "linear", "exponential"]


@dataclass(frozen=True, slots=True)
class CronRetryPolicy:
    """Retry policy for a cron job run."""

    max_attempts: int = 1
    backoff: CronBackoffMode = "none"
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0


@dataclass(frozen=True, slots=True)
class CronJob:
    """Declarative cron job loaded from jobs.yaml."""

    name: str
    schedule: str
    prompt: str
    enabled: bool = True
    session: CronSessionMode = "isolated"
    delivery: CronDeliveryMode = "isolated"
    project: str = ""
    model: str = ""
    provider: str = ""
    permission: str = "default"
    yes_all: bool = False
    no_stream: bool = False
    debug_events: bool = False
    session_id: str = ""
    record_dir: str = ""
    retry: CronRetryPolicy = field(default_factory=CronRetryPolicy)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CronRunRecord:
    """One persisted cron run attempt."""

    run_id: str
    job_name: str
    task_id: str
    session_id: str
    delivery: CronDeliveryMode
    status: str
    attempt: int
    started_at: str
    finished_at: str
    target_session_id: str = ""
    target_record_dir: str = ""
    error: str = ""


@dataclass(frozen=True, slots=True)
class HeartbeatConfig:
    """Configuration for the cron heartbeat loop."""

    enabled: bool = True
    interval_seconds: float = 30.0


@dataclass(frozen=True, slots=True)
class ScheduledRun:
    """A job selected for a concrete schedule instant."""

    job: CronJob
    due_at: datetime
    due_key: str
