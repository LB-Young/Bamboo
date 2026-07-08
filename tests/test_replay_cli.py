"""CLI replay behavior tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bamboo.memory.get_memory_path import get_date_memory_path
from bamboo.memory.session_store import SessionMemoryStore
from bamboo.run import app


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    return home_dir


def test_replay_without_session_id_lists_recent_sessions() -> None:
    _create_session_record(session_id="session-a", prompt="first question")

    result = CliRunner().invoke(app, ["replay"])

    assert result.exit_code == 0
    assert "sessions" in result.output
    assert "Use: bamboo replay SESSION_ID | bamboo replay -1 | bamboo replay latest" in result.output
    assert "-1" in result.output
    assert "session-a" in result.output
    assert "first" in result.output
    assert "question" in result.output


def test_replay_latest_uses_most_recent_session() -> None:
    _create_session_record(session_id="session-latest", prompt="latest question", answer="latest answer")

    result = CliRunner().invoke(app, ["replay", "latest"])

    assert result.exit_code == 0
    assert "session session-latest" in result.output
    assert "latest answer" in result.output


def test_replay_negative_index_selects_recent_session_by_position() -> None:
    _create_session_record(
        session_id="session-older",
        prompt="older question",
        answer="older answer",
        updated_at="2026-07-08T01:00:00+00:00",
    )
    _create_session_record(
        session_id="session-newer",
        prompt="newer question",
        answer="newer answer",
        updated_at="2026-07-08T02:00:00+00:00",
    )

    newest = CliRunner().invoke(app, ["replay", "-1"])
    previous = CliRunner().invoke(app, ["replay", "-2"])

    assert newest.exit_code == 0
    assert "session session-newer" in newest.output
    assert "newer answer" in newest.output
    assert previous.exit_code == 0
    assert "session session-older" in previous.output
    assert "older answer" in previous.output


def test_replay_list_shows_negative_indices_and_session_topics() -> None:
    _create_session_record(
        session_id="session-older",
        prompt="older topic",
        updated_at="2026-07-08T01:00:00+00:00",
    )
    _create_session_record(
        session_id="session-newer",
        prompt="newer topic",
        updated_at="2026-07-08T02:00:00+00:00",
    )

    result = CliRunner().invoke(app, ["replay", "list"])

    assert result.exit_code == 0
    assert "-1" in result.output
    assert "session-newer" in result.output
    assert "newer topic" in result.output
    assert "-2" in result.output
    assert "session-older" in result.output
    assert "older topic" in result.output


def _create_session_record(
    *,
    session_id: str,
    prompt: str,
    answer: str = "done",
    updated_at: str | None = None,
) -> Path:
    memory_dir = get_date_memory_path()
    record_dir = memory_dir / session_id
    store = SessionMemoryStore(memory_dir=memory_dir, session_id=session_id, record_dir=record_dir)
    store.save_session(
        mode="chat",
        project_root=Path.cwd(),
        model="test-model",
        provider="deepseek",
        system_prompt="system",
        metadata={"prompt_mode": "chat"},
    )
    if updated_at is not None:
        session_json = record_dir / "session.json"
        payload = json.loads(session_json.read_text(encoding="utf-8"))
        payload["created_at"] = updated_at
        payload["updated_at"] = updated_at
        session_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    store._append_jsonl(
        record_dir / "messages.jsonl",
        {
            "role": "user",
            "content": prompt,
            "message_id": "m1",
            "agent_name": "",
            "message_type": "normal",
            "active_for_prompt": True,
            "compressed": False,
            "origin_message_ids": [],
            "metadata": {},
            "tool_calls": [],
            "tool_call_id": "",
            "tool_name": "",
        },
    )
    store._append_jsonl(
        record_dir / "messages.jsonl",
        {
            "role": "assistant",
            "content": answer,
            "message_id": "m2",
            "agent_name": "test",
            "message_type": "normal",
            "active_for_prompt": True,
            "compressed": False,
            "origin_message_ids": [],
            "metadata": {},
            "tool_calls": [],
            "tool_call_id": "",
            "tool_name": "",
        },
    )
    store._append_jsonl(record_dir / "events.jsonl", {"type": "task-create", "session_id": session_id, "task_id": "task"})
    store._append_jsonl(
        record_dir / "turns.jsonl",
        {"task_id": "task", "status": "completed", "user_message": prompt, "assistant_answer": answer, "error": ""},
    )
    return record_dir
