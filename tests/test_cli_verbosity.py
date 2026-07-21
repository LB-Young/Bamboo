"""CLI verbosity rendering tests."""

from __future__ import annotations

from bamboo.adapters.cli import main as cli_main
from bamboo.helpers.constant import TaskCreateEvent, TextDeltaEvent, ToolCallEvent, ToolResultEvent
from bamboo.helpers.requests_params import RunParams


def test_simple_verbosity_keeps_text_and_tools_but_suppresses_state(monkeypatch) -> None:
    rendered: list[str] = []
    monkeypatch.setattr(cli_main.console, "print", lambda *parts, **_: rendered.append(" ".join(map(str, parts))))
    renderer = cli_main._cli_event_renderer(RunParams(verbosity="simple"))

    renderer(TaskCreateEvent(session_id="s", task_id="t", title="hidden task"))
    renderer(TextDeltaEvent(session_id="s", delta="hidden assistant text"))
    renderer(ToolCallEvent(session_id="s", tool_name="bash", tool_input={"command": "pwd"}))
    renderer(ToolResultEvent(session_id="s", tool_name="bash", output="returncode: 0\nstdout:\n/tmp"))

    output = "\n".join(rendered)
    assert "hidden task" not in output
    assert "hidden assistant text" in output
    assert "tool call" in output
    assert "tool result" in output
    assert "bash" in output


def test_full_verbosity_keeps_state_and_text_events(monkeypatch) -> None:
    rendered: list[str] = []
    monkeypatch.setattr(cli_main.console, "print", lambda *parts, **_: rendered.append(" ".join(map(str, parts))))
    renderer = cli_main._cli_event_renderer(RunParams(verbosity="full"))

    renderer(TaskCreateEvent(session_id="s", task_id="t", title="visible task"))
    renderer(TextDeltaEvent(session_id="s", delta="visible assistant text"))

    output = "\n".join(rendered)
    assert "visible task" in output
    assert "visible assistant text" in output


def test_medium_verbosity_keeps_text_and_tools_but_suppresses_state(monkeypatch) -> None:
    rendered: list[str] = []
    monkeypatch.setattr(cli_main.console, "print", lambda *parts, **_: rendered.append(" ".join(map(str, parts))))
    renderer = cli_main._cli_event_renderer(RunParams(verbosity="medium"))

    renderer(TaskCreateEvent(session_id="s", task_id="t", title="hidden task"))
    renderer(TextDeltaEvent(session_id="s", delta="visible assistant text"))
    renderer(ToolCallEvent(session_id="s", tool_name="bash", tool_input={"command": "pwd"}))

    output = "\n".join(rendered)
    assert "hidden task" not in output
    assert "visible assistant text" in output
    assert "tool call" in output
