"""Cron job configuration, state and logs."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from bamboo.cron.models import CronJob, CronRetryPolicy, CronRunRecord
from bamboo.userspace.userspace import get_userspace_dir


class CronStore:
    """Filesystem store for cron jobs, state and run logs."""

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or get_userspace_dir()
        self.cron_dir = self.root / "cron"
        self.jobs_path = self.cron_dir / "jobs.yaml"
        self.state_path = self.cron_dir / "state.json"
        self.logs_path = self.root / "logs" / "cron_runs.jsonl"

    def ensure(self) -> None:
        """Create cron directories and an empty jobs file."""
        self.cron_dir.mkdir(parents=True, exist_ok=True)
        self.logs_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.jobs_path.exists():
            self.jobs_path.write_text("jobs: []\n", encoding="utf-8")
        if not self.state_path.exists():
            self._write_state({})

    def load_jobs(self) -> list[CronJob]:
        """Load enabled and disabled jobs from jobs.yaml."""
        self.ensure()
        raw = yaml.safe_load(self.jobs_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("cron jobs file must be a mapping")
        jobs = raw.get("jobs", [])
        if not isinstance(jobs, list):
            raise ValueError("cron jobs file field `jobs` must be a list")
        return [_parse_job(item) for item in jobs]

    def save_jobs(self, jobs: list[CronJob]) -> None:
        """Persist jobs.yaml."""
        self.ensure()
        payload = {"jobs": [_job_to_dict(job) for job in jobs]}
        self.jobs_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def register_job(self, job: CronJob, *, replace: bool = False) -> None:
        """Add a cron job. Existing names require replace=True."""
        jobs = self.load_jobs()
        existing_index = next((index for index, item in enumerate(jobs) if item.name == job.name), None)
        if existing_index is not None:
            if not replace:
                raise ValueError(f"cron job already exists: {job.name}")
            jobs[existing_index] = job
        else:
            jobs.append(job)
        self.save_jobs(jobs)

    def set_enabled(self, name: str, enabled: bool) -> CronJob:
        """Enable or disable one cron job."""
        jobs = self.load_jobs()
        updated: list[CronJob] = []
        changed: CronJob | None = None
        for job in jobs:
            if job.name == name:
                changed = replace(job, enabled=enabled)
                updated.append(changed)
            else:
                updated.append(job)
        if changed is None:
            raise ValueError(f"cron job not found: {name}")
        self.save_jobs(updated)
        return changed

    def load_state(self) -> dict[str, Any]:
        """Load scheduler state."""
        self.ensure()
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save_last_due_key(self, job_name: str, due_key: str) -> None:
        """Record the latest schedule instant selected for a job."""
        state = self.load_state()
        state.setdefault("jobs", {})
        state["jobs"].setdefault(job_name, {})
        state["jobs"][job_name]["last_due_key"] = due_key
        state["jobs"][job_name]["updated_at"] = utc_now_iso()
        self._write_state(state)

    def last_due_key(self, job_name: str) -> str:
        """Return the latest schedule instant selected for a job."""
        state = self.load_state()
        jobs = state.get("jobs", {})
        if not isinstance(jobs, dict):
            return ""
        job_state = jobs.get(job_name, {})
        if not isinstance(job_state, dict):
            return ""
        value = job_state.get("last_due_key", "")
        return str(value or "")

    def append_run(self, record: CronRunRecord) -> None:
        """Append one cron run record to jsonl logs."""
        self.ensure()
        with self.logs_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def load_runs(self) -> list[dict[str, Any]]:
        """Load cron run logs."""
        if not self.logs_path.exists():
            return []
        return [
            json.loads(line)
            for line in self.logs_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _write_state(self, state: dict[str, Any]) -> None:
        self.cron_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def utc_now_iso() -> str:
    """Return current UTC time in stable ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _parse_job(value: Any) -> CronJob:
    if not isinstance(value, dict):
        raise ValueError("cron job entry must be a mapping")
    retry_value = value.get("retry", {})
    if retry_value in (None, ""):
        retry_value = {}
    if not isinstance(retry_value, dict):
        raise ValueError("cron job retry must be a mapping")
    retry = CronRetryPolicy(
        max_attempts=_positive_int(retry_value.get("max_attempts", 1), "retry.max_attempts"),
        backoff=str(retry_value.get("backoff") or "none"),  # type: ignore[arg-type]
        initial_delay_seconds=float(retry_value.get("initial_delay_seconds", 1.0)),
        max_delay_seconds=float(retry_value.get("max_delay_seconds", 60.0)),
    )
    if retry.backoff not in {"none", "linear", "exponential"}:
        raise ValueError("retry.backoff must be none/linear/exponential")
    session = str(value.get("session") or "isolated")
    if session not in {"isolated", "main"}:
        raise ValueError("cron job session must be isolated/main")
    delivery = str(value.get("delivery") or session)
    if delivery not in {"isolated", "main"}:
        raise ValueError("cron job delivery must be isolated/main")
    name = str(value.get("name") or "").strip()
    schedule = str(value.get("schedule") or "").strip()
    prompt = str(value.get("prompt") or "").strip()
    if not name:
        raise ValueError("cron job name is required")
    if not schedule:
        raise ValueError(f"cron job schedule is required: {name}")
    if not prompt:
        raise ValueError(f"cron job prompt is required: {name}")
    return CronJob(
        name=name,
        schedule=schedule,
        prompt=prompt,
        enabled=bool(value.get("enabled", True)),
        session=session,  # type: ignore[arg-type]
        delivery=delivery,  # type: ignore[arg-type]
        project=str(value.get("project") or ""),
        model=str(value.get("model") or ""),
        provider=str(value.get("provider") or ""),
        permission=str(value.get("permission") or "default"),
        yes_all=bool(value.get("yes_all", False)),
        no_stream=bool(value.get("no_stream", False)),
        debug_events=bool(value.get("debug_events", False)),
        session_id=str(value.get("session_id") or ""),
        record_dir=str(value.get("record_dir") or ""),
        retry=retry,
        metadata=_metadata(value.get("metadata", {})),
    )


def _job_to_dict(job: CronJob) -> dict[str, Any]:
    payload = asdict(job)
    payload["retry"] = asdict(job.retry)
    if not payload["metadata"]:
        payload.pop("metadata")
    return payload


def _metadata(value: Any) -> dict[str, str]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValueError("cron job metadata must be a mapping")
    return {str(key): str(item) for key, item in value.items()}


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value
