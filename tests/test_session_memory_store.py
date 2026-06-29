"""验证完整会话记录写入 memory dates/projects。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bamboo.factory.session import SessionFactory
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.memory.get_memory_path import get_memory_dir_name


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """隔离用户空间，避免写入真实 ~/.bamboo。"""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_chat_session_persists_full_messages_to_memory_dates(tmp_path: Path) -> None:
    """验证 chat 模式保存到 ~/.bamboo/memory/dates。"""
    run_params = RunParams(
        message="hello",
        project=str(tmp_path),
        session_mode=SessionMode.chat,
        task_id="task-1",
        session_id="session-1",
    )
    memory_dir = tmp_path / "home" / ".bamboo" / "memory" / "dates" / "today"
    session = SessionFactory().create(memory_dir_path=memory_dir, run_params=run_params)
    session.add_message("assistant", "hi", agent_name="llm:test")

    session_dirs = [path for path in memory_dir.iterdir() if path.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]
    assert session_dir.name != "session-1"
    assert (session_dir / "session.json").is_file()
    assert (session_dir / "system_prompt.md").is_file()
    messages = _read_jsonl(session_dir / "messages.jsonl")

    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["message_id"]
    assert messages[0]["time"]
    assert messages[0]["task_id"] == "task-1"
    assert messages[0]["content"] == "hello"


def test_project_session_persists_to_memory_projects(tmp_path: Path) -> None:
    """验证 project 模式保存到 ~/.bamboo/memory/projects。"""
    project_root = tmp_path / "demo-project"
    project_root.mkdir()
    memory_dir = tmp_path / "home" / ".bamboo" / "memory" / "projects" / get_memory_dir_name(project_root)
    run_params = RunParams(
        message="inspect project",
        project=str(project_root),
        session_mode=SessionMode.project,
        task_id="task-1",
        session_id="session-project",
    )

    SessionFactory().create(memory_dir_path=memory_dir, run_params=run_params)

    session_dir = memory_dir
    session_data = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
    assert session_data["mode"] == "project"
    assert session_data["project_root"] == str(project_root)
    assert (session_dir / "messages.jsonl").is_file()


def test_compaction_persists_before_and_after_messages(tmp_path: Path) -> None:
    """验证压缩前后内容保存到 compactions.jsonl。"""
    memory_dir = tmp_path / "home" / ".bamboo" / "memory" / "dates" / "today"
    run_params = RunParams(
        message="first",
        project=str(tmp_path),
        session_mode=SessionMode.chat,
        task_id="task-compact",
        session_id="session-compact",
    )
    session = SessionFactory().create(memory_dir_path=memory_dir, run_params=run_params)
    second = session.add_message("assistant", "second", agent_name="llm:test")

    session.replace_messages_with_summary([session.messages[0], second], "short summary", agent_name="summary:test")

    session_dirs = [path for path in memory_dir.iterdir() if path.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]
    compactions = _read_jsonl(session_dir / "compactions.jsonl")
    messages = _read_jsonl(session_dir / "messages.jsonl")

    assert compactions[0]["before_messages"][0]["content"] == "first"
    assert compactions[0]["summary"] == "short summary"
    assert compactions[0]["after_active_message_ids"]
    assert messages[-1]["role"] == "system"
    assert messages[-1]["subtype"] == "compaction"
    assert messages[-1]["content"].startswith("[conversation-summary]")
    assert messages[-1]["compaction"]["before_messages"][0]["content"] == "first"
    assert messages[-1]["compaction"]["after_active_message_ids"]


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
