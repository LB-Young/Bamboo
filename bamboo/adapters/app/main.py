"""Native desktop shell for Bamboo.

The app follows the same broad shape as opencode: a small native window shell
loads a local HTML application, while Python exposes a local runtime bridge.
No HTTP server is started for the desktop app.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import threading
import uuid
import webbrowser
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import anyio

from bamboo.adapters.cli.commands import expand_command_message
from bamboo.adapters.web.session_utils import list_sessions, load_session, serialize_messages
from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import (
    KnowledgeUpdateErrorEvent,
    KnowledgeUpdateEvent,
    LLMRequestEvent,
    LLMResponseEvent,
    PermissionRequestEvent,
    PermissionResultEvent,
    ReasoningDeltaEvent,
    ReasoningFinishEvent,
    ReasoningStartEvent,
    SessionMode,
    SessionStatusChangeEvent,
    StepFinishEvent,
    StepStartEvent,
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
from bamboo.llms.media import image_from_source, images_from_text, merge_images
from bamboo.runtime import TaskRuntime
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.security import PermissionDecision, PermissionRequest, PermissionResolver, PermissionResult
from bamboo.security.permission_resolver import permission_request_id

STATIC_DIR = Path(__file__).parent / "static"

APP_EVENT_PATTERNS = {
    "llm.*",
    "memory.*",
    "task.*",
    "session.*",
    "step.*",
    "text.*",
    "reasoning.*",
    "permission.*",
    "tool.*",
}


class AppDependencyError(RuntimeError):
    """Raised when the native desktop runtime is not installed."""


def launch_app(
    *,
    project: Path | None = None,
    model: str | None = None,
    provider: str | None = None,
    permission: str = "default",
    session_mode: SessionMode | str = SessionMode.chat,
    initial_message: str = "",
    image_paths: list[Path] | None = None,
) -> None:
    """Open the Bamboo desktop application window."""
    setup_logging()
    try:
        import webview
    except ImportError as exc:  # pragma: no cover - depends on local optional extra
        raise AppDependencyError(
            "bamboo app requires pywebview. Install or refresh Bamboo with: pip install -e ."
        ) from exc

    bridge = BambooAppBridge(
        project=project,
        model=model or "",
        provider=provider or "",
        permission=permission,
        session_mode=session_mode,
        initial_message=initial_message,
        image_paths=image_paths or [],
    )
    window = webview.create_window(
        "Bamboo",
        str(STATIC_DIR / "index.html"),
        js_api=bridge,
        width=1260,
        height=820,
        min_size=(920, 620),
    )
    bridge.attach_window(window)
    webview.start(debug=False)


@dataclass(slots=True)
class PendingPermission:
    """A permission decision that is waiting on the desktop UI."""

    event: threading.Event
    decision: Literal["allow", "deny"] = "deny"


class AppPermissionResolver(PermissionResolver):
    """Resolve tool permissions through the desktop bridge."""

    def __init__(self, bridge: BambooAppBridge) -> None:
        self.bridge = bridge

    async def resolve(
        self,
        request: PermissionRequest,
        result: PermissionResult,
        run_params: RunParams,
    ) -> PermissionResult:
        if result.decision != PermissionDecision.ASK:
            return result
        decision = await asyncio.to_thread(self.bridge.wait_for_permission, request)
        if decision == "allow":
            return replace(result, decision=PermissionDecision.ALLOW, reason="user approved permission prompt")
        return replace(result, decision=PermissionDecision.DENY, reason="user denied permission prompt")


class BambooAppBridge:
    """Python API exposed to the local desktop frontend."""

    def __init__(
        self,
        *,
        project: Path | None,
        model: str,
        provider: str,
        permission: str,
        session_mode: SessionMode | str,
        initial_message: str,
        image_paths: list[Path],
    ) -> None:
        self.default_project = Path.cwd()
        self.initial_project_path = str(project) if project is not None else ""
        self.model = model
        self.provider = provider
        self.permission = permission
        self.session_mode = session_mode
        self.initial_message = initial_message
        self.initial_image_paths = [str(path) for path in image_paths]
        self.session_id = str(uuid.uuid4())
        self.active_project = self.default_project
        self.active_session_mode: SessionMode = SessionMode.chat
        self.current_task: Task | None = None
        self.running = False
        self.window: Any = None
        self.pending_permissions: dict[str, PendingPermission] = {}
        self.event_bus = EventBus()
        self.permission_resolver = AppPermissionResolver(self)
        self.runtime = self._create_runtime()
        self.unsubscribe = self.event_bus.subscribe(
            self._handle_event,
            patterns=APP_EVENT_PATTERNS,
            filter_fn=lambda event: event.session_id == self.session_id,
        )

    def attach_window(self, window: Any) -> None:
        """Attach the pywebview window after creation."""
        self.window = window

    def open_external_url(self, url: str) -> dict[str, Any]:
        """Open an HTTP(S) URL outside the embedded desktop webview."""
        normalized = (url or "").strip()
        if not normalized.lower().startswith(("http://", "https://")):
            return {"ok": False, "error": "only http and https links can be opened"}
        opened = webbrowser.open(normalized)
        return {"ok": bool(opened)}

    def get_initial_state(self) -> dict[str, Any]:
        """Return initial app state to the frontend."""
        return {
            "session_id": self.session_id,
            "project_path": self.initial_project_path,
            "mode": "project" if self.initial_project_path else "chat",
            "initial_message": self.initial_message,
            "initial_image_paths": self.initial_image_paths,
            "recent_projects": self.recent_projects(),
            "sessions": self.list_sessions(self.initial_project_path),
            "changes": self.get_changes(self.initial_project_path),
        }

    def list_sessions(self, project_path: str = "") -> list[dict[str, str]]:
        """List persisted sessions for the current desktop scope."""
        project, mode = self._resolve_scope(project_path)
        return list_sessions(mode=mode.value, project_path=project if mode == SessionMode.project else None, limit=80)

    def recent_projects(self) -> list[str]:
        """Return recently used project roots from persisted project sessions."""
        paths: list[str] = []
        seen: set[str] = set()
        for session in list_sessions(mode=SessionMode.project.value, project_path=None, limit=1000):
            if session.get("mode") != SessionMode.project.value:
                continue
            raw = str(session.get("project_root") or "").strip()
            if not raw or raw in seen:
                continue
            seen.add(raw)
            paths.append(raw)
        return paths

    def new_session(self, project_path: str = "") -> dict[str, Any]:
        """Start a new local session without running a task."""
        if self.running:
            return {"ok": False, "error": "task is running"}
        project, mode = self._resolve_scope(project_path)
        self.session_id = str(uuid.uuid4())
        self.active_project = project
        self.active_session_mode = mode
        self.current_task = None
        return {
            "ok": True,
            "session_id": self.session_id,
            "mode": mode.value,
            "project_path": "" if mode == SessionMode.chat else str(project),
            "sessions": self.list_sessions(project_path),
            "changes": self.get_changes(project_path),
        }

    def load_session(self, record_dir: str) -> dict[str, Any]:
        """Load a persisted session and make it the active conversation."""
        if self.running:
            return {"ok": False, "error": "task is running"}
        session = load_session(Path(record_dir).expanduser())
        mode = SessionMode.project if session.context.metadata.get("prompt_mode") == "project" else SessionMode.chat
        project = session.context.project_root.expanduser().resolve(strict=False)
        self.session_id = session.session_id
        self.active_project = project
        self.active_session_mode = mode
        run_params = RunParams(
            platform="app",
            message="",
            project=str(project),
            model=self.model or session.model,
            provider=self.provider or session.provider,
            permission=self.permission,
            session_mode=mode,
            task_id=str(uuid.uuid4()),
            session_id=session.session_id,
        )
        self.current_task = Task(
            platform="app",
            session_id=session.session_id,
            task_id=run_params.task_id,
            user_query="",
            session=session,
            config=self.runtime.task_factory.config,
            run_params=run_params,
            memory_dir=session.context.memory_dir,
            status="completed",
        )
        return {
            "ok": True,
            "session_id": session.session_id,
            "mode": mode.value,
            "project_path": "" if mode == SessionMode.chat else str(project),
            "messages": serialize_messages(session),
            "changes": self.get_changes(str(project) if mode == SessionMode.project else ""),
        }

    def send_message(
        self,
        message: str,
        project_path: str = "",
        image_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run a user message in a background thread."""
        message = (message or "").strip()
        if not message and not image_paths:
            return {"ok": False, "error": "message is empty"}
        if self.running:
            return {"ok": False, "error": "task is running"}
        project, mode = self._resolve_scope(project_path)
        if mode == SessionMode.project and not project.is_dir():
            return {"ok": False, "error": f"Project path does not exist: {project}"}
        if self._scope_changed(project, mode):
            self.session_id = str(uuid.uuid4())
            self.current_task = None
        self.active_project = project
        self.active_session_mode = mode
        expanded = expand_command_message(message, project=str(project))
        if expanded.error:
            return {"ok": False, "error": expanded.error}
        message = expanded.message
        images = merge_images(
            [image_from_source(path) for path in (image_paths or [])],
            images_from_text(message),
        )
        self.running = True
        self._emit_ui(
            {
                "type": "run_start",
                "session_id": self.session_id,
                "mode": mode.value,
                "project_path": "" if mode == SessionMode.chat else str(project),
                "message": message,
            }
        )
        threading.Thread(target=self._run_message, args=(message, images, project, mode), daemon=True).start()
        return {"ok": True, "session_id": self.session_id}

    def submit_permission(self, request_id: str, decision: str) -> dict[str, Any]:
        """Submit an allow/deny permission decision from the UI."""
        pending = self.pending_permissions.get(request_id)
        if pending is None:
            return {"ok": False, "error": "permission request not found"}
        pending.decision = "allow" if decision == "allow" else "deny"
        pending.event.set()
        return {"ok": True}

    def get_changes(self, project_path: str = "") -> dict[str, Any]:
        """Return git working tree changes for the inspector panel."""
        project, mode = self._resolve_scope(project_path)
        if mode != SessionMode.project or not project.is_dir():
            return {"project_path": "", "branch": "", "files": [], "additions": 0, "deletions": 0}
        branch = _run_git(project, ["branch", "--show-current"]).strip()
        names = _changed_files(project)
        files = [_file_diff_summary(project, name) for name in names]
        return {
            "project_path": str(project),
            "branch": branch,
            "files": files,
            "additions": sum(item["additions"] for item in files),
            "deletions": sum(item["deletions"] for item in files),
        }

    def get_diff(self, project_path: str, file_path: str) -> dict[str, Any]:
        """Return a unified diff for a changed file."""
        project, mode = self._resolve_scope(project_path)
        if mode != SessionMode.project or not project.is_dir():
            return {"ok": False, "error": "project path required"}
        diff = _run_git(project, ["diff", "--", file_path])
        if not diff:
            diff = _run_git(project, ["diff", "--cached", "--", file_path])
        return {"ok": True, "file": file_path, "diff": diff}

    def wait_for_permission(self, request: PermissionRequest) -> Literal["allow", "deny"]:
        """Block the worker thread until the frontend resolves the permission."""
        request_id = permission_request_id(request)
        pending = PendingPermission(event=threading.Event())
        self.pending_permissions[request_id] = pending
        pending.event.wait(timeout=300)
        self.pending_permissions.pop(request_id, None)
        return pending.decision

    def _create_runtime(self) -> TaskRuntime:
        runtime = TaskRuntime(event_bus=self.event_bus)
        builder = RuntimeContextBuilder(
            event_bus=self.event_bus,
            llm_factory=runtime.llm_factory,
            permission_resolver=self.permission_resolver,
        )
        runtime.runtime_context_builder = builder
        return runtime

    def _run_message(self, message: str, images: list[Any], project: Path, mode: SessionMode) -> None:
        async def run_turn() -> Task:
            if self.current_task is None:
                params = RunParams(
                    platform="app",
                    message=message,
                    images=images,
                    project=str(project),
                    model=self.model,
                    provider=self.provider,
                    permission=self.permission,
                    session_mode=mode,
                    task_id=str(uuid.uuid4()),
                    session_id=self.session_id,
                )
                task = self.runtime.create_task(params)
            else:
                task = self.runtime.create_followup_task(self.current_task, message, images=images)
            return await self.runtime.run_existing_task(task)

        try:
            self.current_task = anyio.run(run_turn)
        except Exception as exc:  # pragma: no cover - surfaced in desktop UI
            self._emit_ui({"type": "error", "error": str(exc)})
        finally:
            self.running = False
            self._emit_ui(
                {
                    "type": "run_finish",
                    "session_id": self.session_id,
                    "sessions": self.list_sessions("" if self.active_session_mode == SessionMode.chat else str(self.active_project)),
                    "changes": self.get_changes("" if self.active_session_mode == SessionMode.chat else str(self.active_project)),
                }
            )

    def _handle_event(self, event: BaseEvent) -> None:
        payload = _event_payload(event)
        if payload:
            payload.setdefault("session_id", event.session_id)
            payload.setdefault("task_id", event.task_id)
            payload.setdefault("event_id", event.event_id)
            payload.setdefault("parent_event_id", event.parent_event_id)
            payload.setdefault("timestamp", event.timestamp)
            self._emit_ui(payload)

    def _emit_ui(self, payload: dict[str, Any]) -> None:
        if self.window is None:
            return
        script = f"window.BambooDesktop?.onEvent({json.dumps(payload, ensure_ascii=False)});"
        try:
            self.window.evaluate_js(script)
        except Exception:
            pass

    def _resolve_scope(self, project_path: str = "") -> tuple[Path, SessionMode]:
        raw = (project_path or "").strip()
        if not raw:
            return self.default_project, SessionMode.chat
        return Path(raw).expanduser().resolve(strict=False), SessionMode.project

    def _scope_changed(self, project: Path, mode: SessionMode) -> bool:
        return self.current_task is not None and (self.active_project != project or self.active_session_mode != mode)


def _event_payload(event: BaseEvent) -> dict[str, Any]:
    if isinstance(event, LLMRequestEvent):
        return {
            "type": "llm_request",
            "role": event.role,
            "model_name": event.model_name,
            "provider": event.provider,
            "prompt_profile": event.prompt_profile,
            "message_count": event.message_count,
            "tool_count": event.tool_count,
            "system_prompt_chars": event.system_prompt_chars,
            "input_chars": event.input_chars,
            "system_prompt": event.system_prompt,
            "messages": event.messages,
            "full_prompt": event.full_prompt,
        }
    if isinstance(event, LLMResponseEvent):
        return {
            "type": "llm_response",
            "role": event.role,
            "model_name": event.model_name,
            "provider": event.provider,
            "response_model": event.response_model,
            "finish_reason": event.finish_reason,
            "output_chars": event.output_chars,
            "tool_call_count": event.tool_call_count,
            "usage": event.usage,
            "success": event.success,
            "error_type": event.error_type,
            "error": event.error,
        }
    if isinstance(event, TaskCreateEvent):
        return {"type": "task_create", "task_id": event.task_id, "title": event.title}
    if isinstance(event, TaskStatusChangeEvent):
        return {"type": "task_status", "from_status": event.from_status, "to_status": event.to_status}
    if isinstance(event, SessionStatusChangeEvent):
        return {"type": "agent_status", "status": event.status, "reason": event.reason}
    if isinstance(event, StepStartEvent):
        return {"type": "step_start", "step_id": event.step_id}
    if isinstance(event, StepFinishEvent):
        return {"type": "step_finish", "summary": event.summary}
    if isinstance(event, ReasoningStartEvent):
        return {"type": "reasoning_start", "message_id": event.message_id}
    if isinstance(event, ReasoningDeltaEvent):
        return {"type": "reasoning_delta", "text": event.delta}
    if isinstance(event, ReasoningFinishEvent):
        return {"type": "reasoning_finish", "text": event.content, "message_id": event.message_id}
    if isinstance(event, TextDeltaEvent):
        return {"type": "text_delta", "text": event.delta}
    if isinstance(event, TextFinishEvent):
        return {"type": "text_finish", "text": event.content, "message_id": event.message_id}
    if isinstance(event, ToolCallEvent):
        return {
            "type": "tool_call",
            "id": event.tool_call_id,
            "name": event.tool_name,
            "input": event.tool_input,
        }
    if isinstance(event, ToolResultEvent):
        return {
            "type": "tool_result",
            "id": event.tool_call_id,
            "name": event.tool_name,
            "output": event.context_output or event.output,
            "truncated": event.truncated,
        }
    if isinstance(event, ToolErrorEvent):
        return {"type": "tool_error", "id": event.tool_call_id, "name": event.tool_name, "error": event.error}
    if isinstance(event, PermissionRequestEvent):
        return {
            "type": "permission_request",
            "request_id": f"{event.session_id}:{event.task_id}:{event.tool_call_id}",
            "id": event.tool_call_id,
            "name": event.tool_name,
            "risk": event.risk_level,
            "reason": event.reason,
            "requires_confirmation": event.requires_confirmation,
        }
    if isinstance(event, PermissionResultEvent):
        return {
            "type": "permission_result",
            "request_id": f"{event.session_id}:{event.task_id}:{event.tool_call_id}",
            "id": event.tool_call_id,
            "name": event.tool_name,
            "approved": event.approved,
            "decision": event.decision,
            "reason": event.reason,
        }
    if isinstance(event, KnowledgeUpdateEvent):
        return {
            "type": "knowledge_update",
            "scope": event.scope,
            "file": event.file,
            "operation": event.operation,
            "status": event.status,
            "reason": event.reason,
            "content": event.content,
        }
    if isinstance(event, KnowledgeUpdateErrorEvent):
        return {
            "type": "knowledge_error",
            "scope": event.scope,
            "file": event.file,
            "reason": event.reason,
        }
    return {}


def _run_git(cwd: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _changed_files(project: Path) -> list[str]:
    output = _run_git(project, ["status", "--porcelain"])
    files: list[str] = []
    for line in output.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            files.append(path)
    return files


def _file_diff_summary(project: Path, file_path: str) -> dict[str, Any]:
    diff = _run_git(project, ["diff", "--numstat", "--", file_path])
    if not diff:
        diff = _run_git(project, ["diff", "--cached", "--numstat", "--", file_path])
    additions = 0
    deletions = 0
    parts = diff.split()
    if len(parts) >= 2:
        additions = _parse_numstat(parts[0])
        deletions = _parse_numstat(parts[1])
    return {"file": file_path, "additions": additions, "deletions": deletions}


def _parse_numstat(value: str) -> int:
    return int(value) if value.isdigit() else 0
