"""FastAPI application for platform-neutral Bamboo API access."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from bamboo.adapters.cli.commands import expand_command_message
from bamboo.adapters.web.app import _event_payload, _restore_task, _stream_event_patterns
from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SessionMode, TextFinishEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.helpers.utils import BaseEvent
from bamboo.llms.base import LLMImage
from bamboo.llms.media import image_from_source, images_from_text, merge_images
from bamboo.runtime import TaskRuntime
from bamboo.runtime.runtime_context import RuntimeContextBuilder


class ApiChatRequest(BaseModel):
    """Request shape for external platform integrations."""

    message: str
    images: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    mode: str = "chat"
    project_path: str | None = None
    session_id: str | None = None
    record_dir: str | None = None
    model: str = ""
    provider: str = ""
    permission: str = "default"
    yes_all: bool = False
    debug_events: bool = False


def create_app(*, title: str = "Bamboo API") -> FastAPI:
    app = FastAPI(title=title)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/chat")
    async def chat(payload: ApiChatRequest) -> dict[str, Any]:
        task, runtime = _prepare_task(payload)
        final_text = ""

        def capture_final(event: BaseEvent) -> None:
            nonlocal final_text
            if isinstance(event, TextFinishEvent):
                final_text = event.content

        unsubscribe = runtime.event_bus.subscribe(
            capture_final,
            patterns={"text.*"},
            filter_fn=lambda event: event.session_id == task.session_id,
        )
        try:
            task = await runtime.run_existing_task(task)
        finally:
            unsubscribe()

        return {
            "session_id": task.session_id,
            "task_id": task.task_id,
            "record_dir": str(task.session.memory_store.session_dir) if task.session.memory_store else "",
            "status": task.status,
            "message": final_text,
        }

    @app.post("/v1/chat/stream")
    async def chat_stream(payload: ApiChatRequest) -> StreamingResponse:
        task, runtime = _prepare_task(payload)
        queue: asyncio.Queue[BaseEvent | None] = asyncio.Queue()
        unsubscribe = runtime.event_bus.subscribe(
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

        async def event_stream() -> AsyncIterator[bytes]:
            yield _jsonl(
                {
                    "type": "session",
                    "session_id": task.session_id,
                    "task_id": task.task_id,
                    "record_dir": str(task.session.memory_store.session_dir) if task.session.memory_store else "",
                    "mode": _normalize_mode(payload.mode),
                }
            )
            worker = asyncio.create_task(run_task())
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


def _prepare_task(payload: ApiChatRequest) -> tuple[Task, TaskRuntime]:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message cannot be empty")
    mode = _normalize_mode(payload.mode)
    project = _resolve_project(payload.project_path, strict=True) if mode == "project" else Path.cwd()
    expanded = expand_command_message(message, project=project)
    if expanded.error:
        raise HTTPException(status_code=400, detail=expanded.error)
    message = expanded.message
    images = _images_from_payload(payload)
    event_bus = EventBus()
    runtime = TaskRuntime(event_bus=event_bus)
    runtime.runtime_context_builder = RuntimeContextBuilder(
        event_bus=event_bus,
        llm_factory=runtime.llm_factory,
    )

    if payload.session_id:
        task = _restore_task(
            runtime=runtime,
            session_id=payload.session_id,
            message=message,
            images=images,
            mode=mode,
            project_path=project,
            record_dir=payload.record_dir,
        )
        task.run_params.model = payload.model
        task.run_params.provider = payload.provider
        task.run_params.permission = payload.permission or "default"
        task.run_params.yes_all = payload.yes_all
        return task, runtime

    run_params = RunParams(
        platform="api",
        message=message,
        images=images,
        project=str(project),
        model=payload.model,
        provider=payload.provider,
        permission=payload.permission or "default",
        yes_all=payload.yes_all,
        session_mode=SessionMode.project if mode == "project" else SessionMode.chat,
        task_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
    )
    return runtime.create_task(run_params), runtime


def _images_from_payload(payload: ApiChatRequest) -> list[LLMImage]:
    return merge_images(
        [image_from_source(source) for source in [*payload.images, *payload.image_paths]],
        images_from_text(payload.message),
    )


def _normalize_mode(mode: str) -> str:
    return "project" if mode == "project" else "chat"


def _resolve_project(path_str: str | None, *, strict: bool) -> Path:
    path = Path(path_str).expanduser() if path_str else Path.cwd()
    if strict and (not path.exists() or not path.is_dir()):
        raise HTTPException(status_code=400, detail=f"project path does not exist: {path}")
    return path.resolve(strict=False)


def _jsonl(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


class _SyntheticError(BaseEvent):
    def __init__(self, session_id: str, task_id: str, message: str) -> None:
        super().__init__(type="error", session_id=session_id, task_id=task_id)
        self.message = message


class _SyntheticCancelled(BaseEvent):
    def __init__(self, session_id: str, task_id: str, message: str) -> None:
        super().__init__(type="cancelled", session_id=session_id, task_id=task_id)
        self.message = message


app = create_app()
