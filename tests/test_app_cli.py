"""CLI tests for the native Bamboo app command."""

from __future__ import annotations

from typer.testing import CliRunner

from bamboo.adapters.app import AppDependencyError
from bamboo.adapters.app.main import _event_payload, _parse_numstat
from bamboo.helpers.constant import ReasoningDeltaEvent, SessionMode, ToolResultEvent
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


def test_app_numstat_parser_ignores_binary_markers() -> None:
    assert _parse_numstat("12") == 12
    assert _parse_numstat("-") == 0
