"""FastAPI application for the Bamboo web chat entry."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bamboo.adapters.cli.commands import expand_command_message
from bamboo.factory.event_bus import get_event_bus
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import (
    CronJobCompleteEvent,
    CronJobStartEvent,
    PermissionRequestEvent,
    PermissionResultEvent,
    SessionMode,
    SessionStatusChangeEvent,
    StepFinishEvent,
    StepStartEvent,
    SubagentFinishEvent,
    SubagentStartEvent,
    TaskCreateEvent,
    TaskStatusChangeEvent,
    TextDeltaEvent,
    TextFinishEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
)
from bamboo.helpers.logging import setup_logging
from bamboo.helpers.requests_params import RunParams
from bamboo.helpers.utils import BaseEvent
from bamboo.runtime import TaskRuntime
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.runtime.store import get_task_store
from bamboo.security import WebPermissionResolver

from .session_utils import list_sessions, load_session, resolve_session_record, serialize_messages

STATIC_DIR = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    message: str
    mode: str = "chat"
    project_path: str | None = None
    session_id: str | None = None
    record_dir: str | None = None
    debug_events: bool = False


class PermissionApprovalRequest(BaseModel):
    decision: str


def create_app(*, static_dir: Path = STATIC_DIR, title: str = "Bamboo Web") -> FastAPI:
    setup_logging()
    app = FastAPI(title=title, docs_url="/openapi-docs")
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.state.permission_resolver = WebPermissionResolver()
    app.state.running_tasks = {}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/docs", response_class=HTMLResponse)
    async def docs() -> str:
        docs_path = static_dir / "docs.html"
        if not docs_path.is_file():
            docs_path = STATIC_DIR / "docs.html"
        return docs_path.read_text(encoding="utf-8")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/sidebar")
    async def sidebar(
        mode: str = Query("chat"),
        project_path: str | None = Query(None),
    ) -> dict[str, Any]:
        normalized_mode = _normalize_mode(mode)
        project = _resolve_project(project_path, strict=False) if normalized_mode == "project" else None
        return {
            "mode": normalized_mode,
            "project_path": str(project) if project else None,
            "sessions": list_sessions(mode=normalized_mode, project_path=project),
        }

    @app.get("/api/sessions/{session_id}")
    async def session_messages(
        session_id: str,
        mode: str = Query("chat"),
        project_path: str | None = Query(None),
        record_dir: str | None = Query(None),
    ) -> dict[str, Any]:
        normalized_mode = _normalize_mode(mode)
        project = _resolve_project(project_path, strict=False) if normalized_mode == "project" else None
        resolved = resolve_session_record(
            session_id,
            mode=normalized_mode,
            project_path=project,
            record_dir=record_dir,
        )
        if resolved is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session = load_session(resolved)
        return {
            "session_id": session.session_id,
            "record_dir": str(resolved),
            "messages": serialize_messages(session),
        }

    @app.post("/api/permissions/{request_id}")
    async def submit_permission(request_id: str, payload: PermissionApprovalRequest) -> dict[str, Any]:
        decision = payload.decision.strip().lower()
        if decision not in {"allow", "deny"}:
            raise HTTPException(status_code=400, detail="decision must be allow or deny")
        accepted = await app.state.permission_resolver.submit(request_id, decision)
        return {"accepted": accepted, "request_id": request_id, "decision": decision}

    @app.post("/api/tasks/{task_id}/stop")
    async def stop_task(task_id: str) -> dict[str, Any]:
        worker: asyncio.Task | None = app.state.running_tasks.get(task_id)
        if worker is not None and not worker.done():
            worker.cancel()
            return {"accepted": True, "task_id": task_id, "status": "cancelling"}
        snapshot = get_task_store().stop(task_id, "cancelled by user")
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"accepted": True, "task_id": task_id, "status": snapshot.status}

    @app.post("/api/chat/stream")
    async def chat_stream(payload: ChatRequest) -> StreamingResponse:
        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="消息不能为空")
        mode = _normalize_mode(payload.mode)
        project = _resolve_project(payload.project_path, strict=True) if mode == "project" else Path.cwd()
        expanded = expand_command_message(message, project=project)
        if expanded.error:
            raise HTTPException(status_code=400, detail=expanded.error)
        message = expanded.message
        event_bus = get_event_bus()
        runtime = TaskRuntime(event_bus=event_bus)
        runtime.runtime_context_builder = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=runtime.llm_factory,
            permission_resolver=app.state.permission_resolver,
        )

        if payload.session_id:
            task = _restore_task(
                runtime=runtime,
                session_id=payload.session_id,
                message=message,
                mode=mode,
                project_path=project,
                record_dir=payload.record_dir,
            )
        else:
            run_params = RunParams(
                platform="web",
                message=message,
                project=str(project),
                permission="default",
                yes_all=False,
                session_mode=SessionMode.project if mode == "project" else SessionMode.chat,
                task_id=str(uuid.uuid4()),
                session_id=str(uuid.uuid4()),
            )
            task = runtime.create_task(run_params)

        queue: asyncio.Queue[BaseEvent | None] = asyncio.Queue()
        unsubscribe = event_bus.subscribe(
            lambda event: queue.put_nowait(event),
            patterns=_stream_event_patterns(debug_events=payload.debug_events),
            filter_fn=lambda event: event.session_id == task.session_id,
        )

        async def run_task() -> None:
            try:
                await runtime.run_existing_task(task)
            except asyncio.CancelledError:
                await queue.put(_SyntheticCancelled(task.session_id, task.task_id, "cancelled by user"))
            except Exception as exc:  # pragma: no cover - streamed to client
                await queue.put(_SyntheticError(task.session_id, task.task_id, str(exc)))
            finally:
                await queue.put(None)
                app.state.running_tasks.pop(task.task_id, None)

        async def event_stream() -> AsyncIterator[bytes]:
            yield _jsonl(
                {
                    "type": "session",
                    "session_id": task.session_id,
                    "task_id": task.task_id,
                    "record_dir": str(task.session.memory_store.session_dir) if task.session.memory_store else "",
                    "mode": mode,
                }
            )
            worker = asyncio.create_task(run_task())
            app.state.running_tasks[task.task_id] = worker
            try:
                while True:
                    event = await queue.get()
                    if event is None:
                        break
                    yield _jsonl(_event_payload(event))
            finally:
                unsubscribe()
                await worker
                yield _jsonl(
                    {
                        "type": "complete",
                        "session_id": task.session_id,
                        "record_dir": str(task.session.memory_store.session_dir) if task.session.memory_store else "",
                    }
                )

        return StreamingResponse(event_stream(), media_type="application/jsonl; charset=utf-8")

    return app


def _restore_task(
    *,
    runtime: TaskRuntime,
    session_id: str,
    message: str,
    mode: str,
    project_path: Path,
    record_dir: str | None,
) -> Task:
    resolved = resolve_session_record(
        session_id,
        mode=mode,
        project_path=project_path if mode == "project" else None,
        record_dir=record_dir,
    )
    if resolved is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session = load_session(resolved)
    base_params = RunParams(
        platform="web",
        message="",
        project=str(project_path),
        permission="default",
        yes_all=False,
        session_mode=SessionMode.project if mode == "project" else SessionMode.chat,
        session_id=session.session_id,
    )
    previous = Task(
        platform="web",
        session_id=session.session_id,
        task_id=str(uuid.uuid4()),
        user_query="",
        session=session,
        config=runtime.task_factory.config,
        run_params=base_params,
        memory_dir=session.memory_store.memory_dir if session.memory_store else resolved.parent,
    )
    return runtime.create_followup_task(previous, message)


def _normalize_mode(mode: str) -> str:
    return "project" if mode == "project" else "chat"


def _resolve_project(path_str: str | None, *, strict: bool) -> Path:
    path = Path(path_str).expanduser() if path_str else Path.cwd()
    if strict and (not path.exists() or not path.is_dir()):
        raise HTTPException(status_code=400, detail=f"项目路径不存在：{path}")
    return path.resolve(strict=False)


def _jsonl(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def _stream_event_patterns(*, debug_events: bool) -> set[str] | str:
    """返回 Web SSE 订阅的事件分类。"""
    if debug_events:
        return "*"
    return {
        "task.*",
        "session.*",
        "step.*",
        "text.*",
        "permission.*",
        "subagent.*",
        "tool.*",
        "cron.*",
    }


def _event_payload(event: BaseEvent) -> dict[str, Any]:
    if isinstance(event, TextDeltaEvent):
        return {"type": "delta", "text": event.delta}
    if isinstance(event, TextFinishEvent):
        return {"type": "message", "text": event.content}
    if isinstance(event, ToolCallEvent):
        return {
            "type": "tool_call",
            "id": event.tool_call_id,
            "name": event.tool_name,
            "input": event.tool_input,
        }
    if isinstance(event, PermissionRequestEvent):
        return {
            "type": "permission_request",
            "request_id": _permission_event_id(event),
            "id": event.tool_call_id,
            "session_id": event.session_id,
            "task_id": event.task_id,
            "name": event.tool_name,
            "risk": event.risk_level,
            "reason": event.reason,
            "requires_confirmation": event.requires_confirmation,
        }
    if isinstance(event, PermissionResultEvent):
        return {
            "type": "permission_result",
            "request_id": _permission_event_id(event),
            "id": event.tool_call_id,
            "session_id": event.session_id,
            "task_id": event.task_id,
            "name": event.tool_name,
            "decision": event.decision,
            "approved": event.approved,
            "risk": event.risk_level,
            "reason": event.reason,
        }
    if isinstance(event, SubagentStartEvent):
        return {
            "type": "subagent_start",
            "name": event.subagent_name,
            "child_task_id": event.child_task_id,
            "parent_session_id": event.parent_session_id,
            "parent_task_id": event.parent_task_id,
            "description": event.description,
        }
    if isinstance(event, SubagentFinishEvent):
        return {
            "type": "subagent_finish",
            "name": event.subagent_name,
            "child_task_id": event.child_task_id,
            "child_session_id": event.child_session_id,
            "parent_session_id": event.parent_session_id,
            "parent_task_id": event.parent_task_id,
            "status": event.status,
        }
    if isinstance(event, ToolResultEvent):
        return {
            "type": "tool_result",
            "id": event.tool_call_id,
            "name": event.tool_name,
            "output": event.output,
        }
    if isinstance(event, ToolErrorEvent):
        return {
            "type": "tool_error",
            "id": event.tool_call_id,
            "name": event.tool_name,
            "error": event.error,
        }
    if isinstance(event, SessionStatusChangeEvent):
        return {"type": "status", "status": event.status, "reason": event.reason}
    if isinstance(event, StepStartEvent):
        return {"type": "step_start", "step_id": event.step_id}
    if isinstance(event, StepFinishEvent):
        return {"type": "step_finish", "summary": event.summary}
    if isinstance(event, TaskCreateEvent):
        return {"type": "task", "task_id": event.task_id, "title": event.title}
    if isinstance(event, TaskStatusChangeEvent):
        return {"type": "task_status", "from": event.from_status, "to": event.to_status}
    if isinstance(event, CronJobStartEvent):
        return {
            "type": "cron_start",
            "job_name": event.job_name,
            "run_id": event.run_id,
            "attempt": event.attempt,
            "delivery": event.delivery,
            "target_session_id": event.target_session_id,
        }
    if isinstance(event, CronJobCompleteEvent):
        return {
            "type": "cron_complete",
            "job_name": event.job_name,
            "run_id": event.run_id,
            "status": event.status,
            "attempt": event.attempt,
            "error": event.error,
            "delivery": event.delivery,
            "target_session_id": event.target_session_id,
        }
    if isinstance(event, _SyntheticError):
        return {"type": "error", "message": event.message}
    if isinstance(event, _SyntheticCancelled):
        return {"type": "cancelled", "message": event.message, "task_id": event.task_id}
    return {"type": "event", "event": event.to_dict()}


def _permission_event_id(event: PermissionRequestEvent | PermissionResultEvent) -> str:
    return f"{event.session_id}:{event.task_id}:{event.tool_call_id}"


class _SyntheticError(BaseEvent):
    def __init__(self, session_id: str, task_id: str, message: str) -> None:
        super().__init__(type="error", session_id=session_id, task_id=task_id)
        self.message = message


class _SyntheticCancelled(BaseEvent):
    def __init__(self, session_id: str, task_id: str, message: str) -> None:
        super().__init__(type="cancelled", session_id=session_id, task_id=task_id)
        self.message = message


app = create_app()
