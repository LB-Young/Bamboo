"""Cron management tools."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from bamboo.cron import CronJob, CronRetryPolicy, CronScheduler, CronStore, cron_matches
from bamboo.tools.buildin.base import Tool, ToolResult


def _job_payload(job: CronJob) -> dict[str, Any]:
    payload = asdict(job)
    payload["retry"] = asdict(job.retry)
    return payload


def _job_line(job: CronJob) -> str:
    status = "enabled" if job.enabled else "disabled"
    project = f" project={job.project}" if job.project else ""
    return f"{job.name} [{status}] {job.schedule} session={job.session}{project} prompt={job.prompt}"


class CronAddTool(Tool):
    """Register or replace a cron job."""

    name = "cron_add"
    description = "Add or replace a Bamboo cron job from conversation."
    risk_level = "write"
    tags = ("cron", "write")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Cron job name."},
                "schedule": {"type": "string", "description": "Five-field cron expression."},
                "prompt": {"type": "string", "description": "Prompt to execute when the job is due."},
                "project": {"type": "string", "description": "Optional project path."},
                "session": {"type": "string", "enum": ["isolated", "main"], "description": "Session mode."},
                "enabled": {"type": "boolean", "description": "Whether the job starts enabled."},
                "permission": {"type": "string", "description": "Permission mode for job runs."},
                "yes_all": {"type": "boolean", "description": "Auto-approve tool permissions during job runs."},
                "max_attempts": {"type": "integer", "description": "Retry attempts."},
                "backoff": {"type": "string", "enum": ["none", "linear", "exponential"], "description": "Retry backoff."},
                "replace": {"type": "boolean", "description": "Replace existing job with the same name."},
            },
            "required": ["name", "schedule", "prompt"],
        }

    async def execute(
        self,
        name: str,
        schedule: str,
        prompt: str,
        project: str = "",
        session: str = "isolated",
        enabled: bool = True,
        permission: str = "default",
        yes_all: bool = False,
        max_attempts: int = 1,
        backoff: str = "none",
        replace: bool = False,
    ) -> ToolResult:
        try:
            cron_matches(schedule, _sample_datetime())
        except Exception as exc:
            return ToolResult(content=f"Invalid cron schedule: {exc}", success=False, error="invalid_schedule")
        if session not in {"isolated", "main"}:
            return ToolResult(content="session must be isolated/main", success=False, error="invalid_session")
        if backoff not in {"none", "linear", "exponential"}:
            return ToolResult(content="backoff must be none/linear/exponential", success=False, error="invalid_backoff")
        if max_attempts <= 0:
            return ToolResult(content="max_attempts must be positive", success=False, error="invalid_retry")

        job = CronJob(
            name=name.strip(),
            schedule=schedule.strip(),
            prompt=prompt.strip(),
            enabled=enabled,
            session=session,  # type: ignore[arg-type]
            project=str(Path(project).expanduser()) if project else "",
            permission=permission or "default",
            yes_all=yes_all,
            retry=CronRetryPolicy(max_attempts=max_attempts, backoff=backoff),  # type: ignore[arg-type]
        )
        try:
            CronStore().register_job(job, replace=replace)
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False, error="cron_job_exists")
        return ToolResult(
            content=f"Registered cron job.\n{_job_line(job)}",
            metadata={"job": _job_payload(job)},
        )


class CronListTool(Tool):
    """List cron jobs."""

    name = "cron_list"
    description = "List Bamboo cron jobs."
    risk_level = "read"
    tags = ("cron", "read")

    async def execute(self) -> ToolResult:
        jobs = CronStore().load_jobs()
        if not jobs:
            return ToolResult(content="(no cron jobs)", metadata={"jobs": []})
        return ToolResult(
            content="\n".join(_job_line(job) for job in jobs),
            metadata={"jobs": [_job_payload(job) for job in jobs]},
        )


class CronGetTool(Tool):
    """Get one cron job."""

    name = "cron_get"
    description = "Get a Bamboo cron job by name."
    risk_level = "read"
    tags = ("cron", "read")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Cron job name."}},
            "required": ["name"],
        }

    async def execute(self, name: str) -> ToolResult:
        for job in CronStore().load_jobs():
            if job.name == name:
                return ToolResult(content=_job_line(job), metadata={"job": _job_payload(job)})
        return ToolResult(content=f"Cron job not found: {name}", success=False, error="cron_job_not_found")


class CronEnableTool(Tool):
    """Enable a cron job."""

    name = "cron_enable"
    description = "Enable a Bamboo cron job."
    risk_level = "write"
    tags = ("cron", "write")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Cron job name."}},
            "required": ["name"],
        }

    async def execute(self, name: str) -> ToolResult:
        try:
            job = CronStore().set_enabled(name, True)
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False, error="cron_job_not_found")
        return ToolResult(content=f"Enabled cron job.\n{_job_line(job)}", metadata={"job": _job_payload(job)})


class CronDisableTool(Tool):
    """Disable a cron job."""

    name = "cron_disable"
    description = "Disable a Bamboo cron job."
    risk_level = "write"
    tags = ("cron", "write")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Cron job name."}},
            "required": ["name"],
        }

    async def execute(self, name: str) -> ToolResult:
        try:
            job = CronStore().set_enabled(name, False)
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False, error="cron_job_not_found")
        return ToolResult(content=f"Disabled cron job.\n{_job_line(job)}", metadata={"job": _job_payload(job)})


class CronRunsTool(Tool):
    """Read cron run logs."""

    name = "cron_runs"
    description = "List recent Bamboo cron run records."
    risk_level = "read"
    tags = ("cron", "read")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Maximum run records."}},
            "required": [],
        }

    async def execute(self, limit: int = 20) -> ToolResult:
        runs = CronStore().load_runs()
        runs = runs[-max(limit, 1):]
        if not runs:
            return ToolResult(content="(no cron runs)", metadata={"runs": []})
        lines = [
            f"{item.get('job_name')} [{item.get('status')}] attempt={item.get('attempt')} task={item.get('task_id')}"
            for item in runs
        ]
        return ToolResult(content="\n".join(lines), metadata={"runs": runs})


class CronTickTool(Tool):
    """Run one scheduler tick from conversation."""

    name = "cron_tick"
    description = "Run one Bamboo cron scheduler tick now."
    risk_level = "write"
    tags = ("cron", "write")

    async def execute(self) -> ToolResult:
        records = await CronScheduler().tick()
        if not records:
            return ToolResult(content="No cron jobs were due.", metadata={"runs": []})
        return ToolResult(
            content="\n".join(f"{record.job_name} [{record.status}] attempt={record.attempt}" for record in records),
            metadata={"runs": [asdict(record) for record in records]},
        )


def _sample_datetime():
    from datetime import datetime, timezone

    return datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
