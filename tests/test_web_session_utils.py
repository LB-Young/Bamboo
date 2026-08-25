"""Tests for Bamboo web session restore helpers."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from bamboo.adapters.web import session_utils
from bamboo.adapters.web.session_utils import load_session, list_sessions, serialize_messages
from bamboo.memory.session_store import SessionRecord


def test_load_session_restores_tool_calls_as_objects(tmp_path: Path) -> None:
    record_dir = tmp_path / "record"
    record_dir.mkdir()
    (record_dir / "session.json").write_text(
        json.dumps(
            {
                "session_id": "session-1",
                "memory_dir": str(tmp_path),
                "project_root": str(tmp_path),
                "model": "test-model",
                "provider": "test-provider",
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    (record_dir / "system_prompt.md").write_text("system", encoding="utf-8")
    (record_dir / "messages.jsonl").write_text(
        json.dumps(
            {
                "role": "assistant",
                "content": "using tool",
                "message_id": "message-1",
                "time": "2026-06-30T00:00:00+00:00",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "name": "glob",
                        "arguments": {"pattern": "*.pdf"},
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    session = load_session(record_dir)

    assert session.messages[0].tool_calls[0].id == "call-1"
    assert session.messages[0].tool_calls[0].name == "glob"
    assert session.messages[0].tool_calls[0].arguments == {"pattern": "*.pdf"}


def test_serialize_messages_includes_reasoning_metadata(tmp_path: Path) -> None:
    record_dir = tmp_path / "record"
    record_dir.mkdir()
    (record_dir / "session.json").write_text(
        json.dumps(
            {
                "session_id": "session-1",
                "memory_dir": str(tmp_path),
                "project_root": str(tmp_path),
                "model": "test-model",
                "provider": "test-provider",
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    (record_dir / "system_prompt.md").write_text("system", encoding="utf-8")
    (record_dir / "messages.jsonl").write_text(
        json.dumps(
            {
                "role": "assistant",
                "content": "最终答案",
                "message_id": "message-1",
                "time": "2026-06-30T00:00:00+00:00",
                "metadata": {"reasoning_content": "推理过程"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    messages = serialize_messages(load_session(record_dir))

    assert messages[0]["content"] == "最终答案"
    assert messages[0]["metadata"] == {"reasoning_content": "推理过程"}


def test_list_sessions_deduplicates_same_session_id(monkeypatch, tmp_path: Path) -> None:
    newer = SessionRecord(
        session_id="same-session",
        mode="project",
        label="newer",
        created_at="2026-08-21T01:00:00+00:00",
        updated_at="2026-08-21T01:10:00+00:00",
        record_dir=tmp_path / "newer",
        memory_dir=tmp_path,
        project_root=tmp_path,
        metadata={"platform": "app"},
    )
    older = replace(
        newer,
        label="older",
        updated_at="2026-08-21T01:00:00+00:00",
        record_dir=tmp_path / "older",
    )

    def fake_list_session_records(**kwargs):
        return [newer, older]

    monkeypatch.setattr(session_utils, "list_session_records", fake_list_session_records)

    sessions = list_sessions(mode="project", project_path=tmp_path, limit=40)

    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "same-session"
    assert sessions[0]["label"] == "newer"
    assert sessions[0]["record_dir"] == str(tmp_path / "newer")
