"""Polished native desktop shell for Bamboo.

This adapter intentionally keeps its frontend separate from
``bamboo.adapters.app`` while reusing the same runtime bridge.
"""

from __future__ import annotations

import asyncio
import platform
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from bamboo.adapters.app.main import AppDependencyError, BambooAppBridge, _parse_numstat
from bamboo.adapters.cli.commands import expand_command_message
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import LLMResponseEvent, SessionMode
from bamboo.helpers.logging import setup_logging
from bamboo.helpers.requests_params import RunParams
from bamboo.llms.media import image_from_source, images_from_text, merge_images
from bamboo.prompts import build_system_prompt
from bamboo.runtime.context_compactor import HeuristicTokenCounter

STATIC_DIR = Path(__file__).parent / "static"
ASSET_DIR = STATIC_DIR / "assets"
WINDOWS_APP_USER_MODEL_ID = "YoungL.Bamboo.AppFancy"


def _app_icon_path() -> Path:
    """Return a pywebview-compatible app icon for the current platform."""
    system = platform.system()
    if system == "Windows":
        return ASSET_DIR / "bamboo_app_icon.ico"
    if system == "Darwin":
        return ASSET_DIR / "bamboo_app_icon.icns"
    return ASSET_DIR / "bamboo_app_icon.png"


def _set_windows_app_user_model_id() -> None:
    """Give Windows a stable app identity so taskbar icons do not group under python.exe."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_USER_MODEL_ID)
    except Exception:
        return


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
    """Open the polished Bamboo desktop application window."""
    setup_logging()
    _set_windows_app_user_model_id()
    try:
        import webview
    except ImportError as exc:  # pragma: no cover - depends on local optional extra
        raise AppDependencyError(
            "bamboo app-fancy requires pywebview. Install or refresh Bamboo with: pip install -e ."
        ) from exc

    bridge = BambooFancyAppBridge(
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
        width=1440,
        height=900,
        min_size=(1120, 720),
    )
    bridge.attach_window(window)
    webview.start(debug=False, icon=str(_app_icon_path()))


class BambooFancyAppBridge(BambooAppBridge):
    """Desktop bridge with richer data for the fancy UI."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.startup_model = self.model
        self.latest_usage: dict[str, int] = {}
        self.token_counter = HeuristicTokenCounter()
        self.worker_loop: asyncio.AbstractEventLoop | None = None
        self.worker_task: asyncio.Task[Task] | None = None
        self.worker_lock = threading.Lock()
        self.stop_requested = False
        self.llm_unsubscribe = self.event_bus.subscribe(
            self._handle_llm_event,
            event_types={"llm-response"},
            filter_fn=lambda event: event.session_id == self.session_id,
        )

    def get_initial_state(self) -> dict[str, Any]:
        state = super().get_initial_state()
        state["context"] = self.get_context_usage()
        state["models"] = self.get_model_selector_state()
        return state

    def new_session(self, project_path: str = "") -> dict[str, Any]:
        result = super().new_session(project_path)
        result["context"] = self.get_context_usage()
        result["models"] = self.get_model_selector_state()
        return result

    def load_session(self, record_dir: str) -> dict[str, Any]:
        result = super().load_session(record_dir)
        result["context"] = self.get_context_usage()
        result["models"] = self.get_model_selector_state()
        return result

    def get_model_selector_state(self) -> dict[str, Any]:
        """Return available model registrations and the model selected for new turns."""
        llm_factory = self.runtime.llm_factory
        selected = self._selected_model_name()
        options: list[dict[str, Any]] = []
        for name in llm_factory.list_model_names():
            config = llm_factory.get_model_config(name)
            if config.model_type not in {"text", "vision"}:
                continue
            options.append(
                {
                    "name": name,
                    "provider": config.provider,
                    "model": config.model,
                    "model_type": config.model_type,
                    "context_window": config.context_window,
                }
            )
        return {
            "selected": selected,
            "configured": self._configured_default_model_name(),
            "options": options,
        }

    def send_message(
        self,
        message: str,
        project_path: str = "",
        image_paths: list[str] | None = None,
        model_name: str = "",
    ) -> dict[str, Any]:
        """Run a user message with an optional per-turn model override."""
        message = (message or "").strip()
        if not message and not image_paths:
            return {"ok": False, "error": "message is empty"}
        if self.running:
            return {"ok": False, "error": "task is running"}
        selected_model = self._resolve_requested_model(model_name)
        if selected_model is None:
            return {"ok": False, "error": f"Model is not configured: {model_name}"}
        project, mode = self._resolve_scope(project_path)
        if mode == SessionMode.project and not project.is_dir():
            return {"ok": False, "error": f"Project path does not exist: {project}"}
        if self._scope_changed(project, mode):
            self.session_id = str(uuid.uuid4())
            self.current_task = None
        self.model = selected_model
        self.provider = self.runtime.llm_factory.get_model_config(selected_model).provider
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
        self._apply_selected_model_to_current_session(selected_model, project, mode)
        self.running = True
        self._emit_ui(
            {
                "type": "run_start",
                "session_id": self.session_id,
                "mode": mode.value,
                "project_path": "" if mode == SessionMode.chat else str(project),
                "message": message,
                "model": selected_model,
            }
        )
        threading.Thread(target=self._run_message, args=(message, images, project, mode), daemon=True).start()
        return {"ok": True, "session_id": self.session_id, "model": selected_model}

    def get_changes(self, project_path: str = "") -> dict[str, Any]:
        """Return changed files, expanding untracked directories into concrete files."""
        project, mode = self._resolve_scope(project_path)
        if mode != SessionMode.project or not project.is_dir():
            return {"project_path": "", "branch": "", "files": [], "additions": 0, "deletions": 0}
        branch = _run_git(project, ["branch", "--show-current"]).strip()
        names = _changed_files_expanded(project)
        files = [_file_diff_summary(project, name) for name in names]
        return {
            "project_path": str(project),
            "branch": branch,
            "files": files,
            "additions": sum(item["additions"] for item in files),
            "deletions": sum(item["deletions"] for item in files),
        }

    def get_diff(self, project_path: str, file_path: str) -> dict[str, Any]:
        """Return a real git diff or a synthetic diff for untracked files."""
        project, mode = self._resolve_scope(project_path)
        if mode != SessionMode.project or not project.is_dir():
            return {"ok": False, "error": "project path required"}
        diff = _run_git(project, ["diff", "--", file_path])
        if not diff:
            diff = _run_git(project, ["diff", "--cached", "--", file_path])
        if not diff:
            diff = _untracked_file_diff(project, file_path)
        return {"ok": True, "file": file_path, "diff": diff}

    def get_context_usage(self) -> dict[str, Any]:
        """Return best-effort context usage for the active session."""
        context_window = self._context_window()
        input_tokens = _usage_input_tokens(self.latest_usage)
        output_tokens = _usage_output_tokens(self.latest_usage)
        estimated = self._estimate_session_tokens()
        used = max(input_tokens + output_tokens, estimated)
        percent = min(100, round((used / context_window) * 100)) if context_window else 0
        return {
            "used_tokens": used,
            "context_window": context_window,
            "percent": percent,
            "usage": self.latest_usage,
            "estimated": input_tokens == 0,
        }

    def _handle_llm_event(self, event: Any) -> None:
        if isinstance(event, LLMResponseEvent) and event.usage:
            self.latest_usage = dict(event.usage)
            self._emit_ui({"type": "context_usage", "context": self.get_context_usage()})

    def stop_current_task(self) -> dict[str, Any]:
        """Request cancellation of the currently running desktop task."""
        if not self.running:
            return {"ok": False, "error": "no task is running"}
        self.stop_requested = True
        for pending in list(self.pending_permissions.values()):
            pending.decision = "deny"
            pending.event.set()
        with self.worker_lock:
            loop = self.worker_loop
            task = self.worker_task
        if loop is not None and task is not None and not task.done():
            loop.call_soon_threadsafe(task.cancel)
        self._emit_ui({"type": "cancelled", "message": "cancelled by user"})
        return {"ok": True, "status": "cancelling"}

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

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task = loop.create_task(run_turn())
        with self.worker_lock:
            self.worker_loop = loop
            self.worker_task = task
            if self.stop_requested:
                loop.call_soon(task.cancel)
        try:
            self.current_task = loop.run_until_complete(task)
        except asyncio.CancelledError:
            self._emit_ui({"type": "cancelled", "message": "cancelled by user"})
        except Exception as exc:  # pragma: no cover - surfaced in desktop UI
            if not self.stop_requested:
                self._emit_ui({"type": "error", "error": str(exc)})
        finally:
            with self.worker_lock:
                self.worker_loop = None
                self.worker_task = None
            loop.close()
            self.running = False
            stopped = self.stop_requested
            self.stop_requested = False
            self._emit_ui(
                {
                    "type": "run_finish",
                    "session_id": self.session_id,
                    "cancelled": stopped,
                    "sessions": self.list_sessions("" if self.active_session_mode == SessionMode.chat else str(self.active_project)),
                    "changes": self.get_changes("" if self.active_session_mode == SessionMode.chat else str(self.active_project)),
                }
            )
            self._emit_ui({"type": "context_usage", "context": self.get_context_usage()})

    def _context_window(self) -> int:
        if self.current_task is None:
            raw_models = self.runtime.task_factory.config.get("models", {})
            if isinstance(raw_models, dict):
                model_name = self.model or raw_models.get("default_model", "")
                raw_config = raw_models.get(model_name, {}) if isinstance(model_name, str) else {}
                if isinstance(raw_config, dict):
                    value = raw_config.get("context_window")
                    if isinstance(value, int) and value > 0:
                        return value
            return 128000
        raw_models = self.current_task.config.get("models", {})
        if isinstance(raw_models, dict):
            model_name = self.model or self.current_task.run_params.model or raw_models.get("default_model", "")
            raw_config = raw_models.get(model_name, {}) if isinstance(model_name, str) else {}
            if isinstance(raw_config, dict):
                value = raw_config.get("context_window")
                if isinstance(value, int) and value > 0:
                    return value
        return 128000

    def _estimate_session_tokens(self) -> int:
        if self.current_task is None:
            return 0
        total = self.token_counter.count_text(self.current_task.session.context.system_prompt)
        for message in self.current_task.session.messages:
            total += 4 + self.token_counter.count_text(message.role) + self.token_counter.count_text(message.content)
            total += len(message.images) * 1024
            total += self.token_counter.count_text(message.tool_call_id)
        return total

    def _configured_default_model_name(self) -> str:
        llm_factory = self.runtime.llm_factory
        if self.startup_model and llm_factory.has_model(self.startup_model):
            return self.startup_model
        main_agent_config = self.runtime.task_factory.config.get("bamboo_main_agent", {})
        configured_name = main_agent_config.get("model") if isinstance(main_agent_config, dict) else None
        if isinstance(configured_name, str) and configured_name and llm_factory.has_model(configured_name):
            return configured_name
        return llm_factory.default_model_name

    def _selected_model_name(self) -> str:
        if self.current_task is not None and self.current_task.session.model:
            return self.current_task.session.model
        return self._configured_default_model_name()

    def _resolve_requested_model(self, model_name: str = "") -> str | None:
        selected = (model_name or "").strip() or self._selected_model_name()
        if self.runtime.llm_factory.has_model(selected):
            return selected
        return None

    def _apply_selected_model_to_current_session(self, model_name: str, project: Path, mode: SessionMode) -> None:
        if self.current_task is None:
            return
        config = self.runtime.llm_factory.get_model_config(model_name)
        self.current_task.run_params.model = model_name
        self.current_task.run_params.provider = config.provider
        self.current_task.session.model = model_name
        self.current_task.session.provider = config.provider
        self.current_task.session.context.system_prompt = build_system_prompt(
            session_mode=mode,
            project_root=project,
            memory_dir=self.current_task.memory_dir,
            model=model_name,
            provider=config.provider,
        )
        if self.current_task.session.memory_store is not None:
            self.current_task.session.memory_store.save_session(
                mode=mode.value,
                project_root=project,
                model=model_name,
                provider=config.provider,
                system_prompt=self.current_task.session.context.system_prompt,
                metadata=self.current_task.session.context.metadata,
            )


def _usage_input_tokens(usage: dict[str, int]) -> int:
    for key in ("input_tokens", "prompt_tokens", "total_input_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return 0


def _usage_output_tokens(usage: dict[str, int]) -> int:
    for key in ("output_tokens", "completion_tokens", "total_output_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return 0


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


def _changed_files_expanded(project: Path) -> list[str]:
    output = _run_git(project, ["status", "--porcelain"])
    files: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        if len(line) < 4:
            continue
        status = line[:2]
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if status == "??" and path.endswith("/"):
            candidates = _untracked_files_under(project, path)
        else:
            candidates = [path]
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                files.append(candidate)
    return files


def _untracked_files_under(project: Path, path: str) -> list[str]:
    output = _run_git(project, ["ls-files", "--others", "--exclude-standard", "--", path])
    return [line.strip() for line in output.splitlines() if line.strip()]


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
    if not diff and _is_untracked_file(project, file_path):
        additions = _count_file_lines(project / file_path)
    return {"file": file_path, "additions": additions, "deletions": deletions}


def _is_untracked_file(project: Path, file_path: str) -> bool:
    output = _run_git(project, ["ls-files", "--others", "--exclude-standard", "--", file_path])
    return file_path in {line.strip() for line in output.splitlines()}


def _count_file_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def _untracked_file_diff(project: Path, file_path: str) -> str:
    if not _is_untracked_file(project, file_path):
        return ""
    path = (project / file_path).resolve(strict=False)
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = content.splitlines()
    header = [
        f"diff --git a/{file_path} b/{file_path}",
        "new file mode 100644",
        "index 0000000..0000000",
        "--- /dev/null",
        f"+++ b/{file_path}",
        f"@@ -0,0 +1,{len(lines)} @@",
    ]
    return "\n".join([*header, *(f"+{line}" for line in lines)])
