"""Tests for Bamboo web session restore helpers."""

from __future__ import annotations

import json
from pathlib import Path

from bamboo.adapters.web.session_utils import load_session, serialize_messages


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
