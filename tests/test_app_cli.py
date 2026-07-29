"""CLI tests for the native Bamboo app command."""

from __future__ import annotations

import ctypes
import subprocess
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from bamboo.adapters.app import AppDependencyError
from bamboo.adapters.app.main import BambooAppBridge, _event_payload, _parse_numstat
from bamboo.adapters.app_fancy.main import (
    BambooFancyAppBridge,
    WINDOWS_APP_USER_MODEL_ID,
    _app_icon_path,
    _changed_files_expanded,
    _file_diff_summary,
    _set_windows_app_user_model_id,
    _untracked_file_diff,
)
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import ReasoningDeltaEvent, SessionCompactEvent, SessionMode, ToolResultEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.run import app


def test_app_command_launches_native_adapter(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    cron_started: list[bool] = []
    monkeypatch.setattr("bamboo.run._start_default_cron", lambda: cron_started.append(True))
    monkeypatch.setattr("bamboo.adapters.app.launch_app", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(app, ["app", "--msg", "hello", "--session-mode", "chat"])

    assert result.exit_code == 0
    assert cron_started == [True]
    assert calls == [
        {
            "project": None,
            "model": "",
            "provider": "",
            "permission": "default",
            "session_mode": SessionMode.chat,
            "initial_message": "hello",
            "image_paths": [],
        }
    ]


def test_app_command_reports_missing_desktop_dependency(monkeypatch) -> None:
    monkeypatch.setattr("bamboo.run._start_default_cron", lambda: None)

    def fail_launch(**kwargs) -> None:
        raise AppDependencyError("bamboo app requires pywebview. Install or refresh Bamboo with: pip install -e .")

    monkeypatch.setattr("bamboo.adapters.app.launch_app", fail_launch)

    result = CliRunner().invoke(app, ["app"])

    assert result.exit_code == 1
    assert "pip install -e ." in result.output
    assert "Traceback" not in result.output


def test_app_fancy_command_launches_fancy_adapter(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    cron_started: list[bool] = []
    monkeypatch.setattr("bamboo.run._start_default_cron", lambda: cron_started.append(True))
    monkeypatch.setattr("bamboo.adapters.app_fancy.launch_app", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(
        app,
        [
            "app-fancy",
            "--msg",
            "hello",
            "--project",
            "/tmp/project",
            "--model",
            "kimi-k3",
            "--provider",
            "kimi",
            "--permission",
            "default",
            "--session-mode",
            "project",
        ],
    )

    assert result.exit_code == 0
    assert cron_started == [True]
    assert calls == [
        {
            "project": Path("/tmp/project"),
            "model": "kimi-k3",
            "provider": "kimi",
            "permission": "default",
            "session_mode": SessionMode.project,
            "initial_message": "hello",
            "image_paths": [],
        }
    ]


def test_app_fancy_icon_uses_platform_specific_format(monkeypatch) -> None:
    monkeypatch.setattr("bamboo.adapters.app_fancy.main.platform.system", lambda: "Windows")
    assert _app_icon_path().name == "bamboo_app_icon.ico"

    monkeypatch.setattr("bamboo.adapters.app_fancy.main.platform.system", lambda: "Darwin")
    assert _app_icon_path().name == "bamboo_app_icon.icns"

    monkeypatch.setattr("bamboo.adapters.app_fancy.main.platform.system", lambda: "Linux")
    assert _app_icon_path().name == "bamboo_app_icon.png"


def test_app_fancy_sets_windows_app_user_model_id(monkeypatch) -> None:
    calls: list[str] = []
    shell32 = SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=lambda app_id: calls.append(app_id))
    monkeypatch.setattr("bamboo.adapters.app_fancy.main.platform.system", lambda: "Windows")
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(shell32=shell32), raising=False)

    _set_windows_app_user_model_id()

    assert calls == [WINDOWS_APP_USER_MODEL_ID]


def test_app_fancy_context_usage_tracks_active_prompt_messages(monkeypatch) -> None:
    monkeypatch.setattr(
        BambooFancyAppBridge,
        "_create_runtime",
        lambda self: SimpleNamespace(task_factory=SimpleNamespace(config={})),
    )
    bridge = BambooFancyAppBridge(
        project=None,
        model="",
        provider="",
        permission="default",
        session_mode=SessionMode.chat,
        initial_message="",
        image_paths=[],
    )
    task = TaskFactory().create(RunParams(message="current question", session_id=bridge.session_id))
    inactive = task.session.add_message("assistant", "old detail " * 60000)
    inactive.mark_as_compressed()
    task.session.add_message("system", "[conversation-summary]\nshort summary", message_type="compaction")
    bridge.current_task = task
    bridge.latest_usage = {"input_tokens": 130000, "output_tokens": 7000}

    bridge._handle_llm_event(
        SessionCompactEvent(
            session_id=bridge.session_id,
            task_id=task.task_id,
            before_token_count=130000,
            after_token_count=1000,
        )
    )
    usage = bridge.get_context_usage()

    assert bridge.latest_usage == {}
    assert usage["used_tokens"] < bridge.token_counter.count_text(inactive.content)
    assert usage["percent"] < 100


def test_app_event_payloads_keep_reasoning_and_tools_separate() -> None:
    reasoning = _event_payload(ReasoningDeltaEvent(session_id="session-1", task_id="task-1", delta="推理过程"))
    tool = _event_payload(
        ToolResultEvent(
            session_id="session-1",
            task_id="task-1",
            tool_call_id="call-1",
            tool_name="read",
            output="完整输出",
            context_output="摘要输出",
            truncated=True,
        )
    )

    assert reasoning == {"type": "reasoning_delta", "text": "推理过程"}
    assert tool == {
        "type": "tool_result",
        "id": "call-1",
        "name": "read",
        "output": "摘要输出",
        "truncated": True,
    }


def test_app_bridge_opens_only_external_web_links(monkeypatch) -> None:
    opened_urls: list[str] = []
    monkeypatch.setattr(BambooAppBridge, "_create_runtime", lambda self: SimpleNamespace())
    monkeypatch.setattr("bamboo.adapters.app.main.webbrowser.open", lambda url: opened_urls.append(url) or True)
    bridge = BambooAppBridge(
        project=None,
        model="",
        provider="",
        permission="default",
        session_mode=SessionMode.chat,
        initial_message="",
        image_paths=[],
    )

    assert bridge.open_external_url("https://example.com/docs") == {"ok": True}
    blocked = bridge.open_external_url("file:///etc/passwd")

    assert opened_urls == ["https://example.com/docs"]
    assert blocked["ok"] is False


def test_app_bridge_lists_recent_project_paths(monkeypatch) -> None:
    monkeypatch.setattr(BambooAppBridge, "_create_runtime", lambda self: SimpleNamespace())
    monkeypatch.setattr(
        "bamboo.adapters.app.main.list_sessions",
        lambda **kwargs: [
            {"mode": "project", "project_root": "/tmp/project-a"},
            {"mode": "chat", "project_root": "/tmp/chat-cwd"},
            {"mode": "project", "project_root": "/tmp/project-b"},
            {"mode": "project", "project_root": "/tmp/project-a"},
            {"mode": "project", "project_root": ""},
        ],
    )
    bridge = BambooAppBridge(
        project=None,
        model="",
        provider="",
        permission="default",
        session_mode=SessionMode.chat,
        initial_message="",
        image_paths=[],
    )

    assert bridge.recent_projects() == ["/tmp/project-a", "/tmp/project-b"]


def test_app_numstat_parser_ignores_binary_markers() -> None:
    assert _parse_numstat("12") == 12
    assert _parse_numstat("-") == 0


def test_app_fancy_expands_untracked_directories_and_shows_new_file_diff(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    html = tmp_path / "bayon_note" / "index.html"
    html.parent.mkdir()
    html.write_text("<!doctype html>\n<title>Bayon Note</title>\n", encoding="utf-8")

    assert _changed_files_expanded(tmp_path) == ["bayon_note/index.html"]
    assert _file_diff_summary(tmp_path, "bayon_note/index.html") == {
        "file": "bayon_note/index.html",
        "additions": 2,
        "deletions": 0,
    }

    diff = _untracked_file_diff(tmp_path, "bayon_note/index.html")

    assert "+++ b/bayon_note/index.html" in diff
    assert "+<title>Bayon Note</title>" in diff
