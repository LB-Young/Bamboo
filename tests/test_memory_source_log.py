"""Tests for memory source log scopes and retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest

from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.memory.get_memory_path import get_memory_dir_name
from bamboo.memory.scope import MemoryScope, resolve_memory_scope
from bamboo.memory.session_store import SessionMemoryStore
from bamboo.memory.source_log import search_source_logs


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_memory_scope_resolves_chat_and_project(tmp_path: Path) -> None:
    project_root = tmp_path / "demo-project"
    project_root.mkdir()

    chat_scope = resolve_memory_scope(session_mode=SessionMode.chat.value, project_root=project_root)
    project_scope = resolve_memory_scope(session_mode=SessionMode.project.value, project_root=project_root)

    assert chat_scope.kind == "chat"
    assert chat_scope.root.name == "dates"
    assert project_scope.kind == "project"
    assert project_scope.project_hash == get_memory_dir_name(project_root)
    assert project_scope.root.name == "projects"


def test_append_turn_redacts_and_searches_source_log(tmp_path: Path) -> None:
    scope = MemoryScope.chat()
    session_dir = scope.root / "2026-07-03" / "session-a"
    store = SessionMemoryStore(memory_dir=scope.root / "2026-07-03", session_id="session-a", record_dir=session_dir)
    task = _task_with_messages(
        session_id="session-a",
        task_id="task-a",
        query="remember vector database decision",
        answer="Use sqlite for source log index. api_key=sk-abcdefghijklmnopqrstuvwxyz",
    )
    task.session.memory_store = store

    store.append_turn(task)

    turns = store.load_turns()
    assert turns[0]["user_message"] == "remember vector database decision"
    assert "[REDACTED]" in turns[0]["assistant_answer"]
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in turns[0]["assistant_answer"]

    matches = search_source_logs("sqlite source", scope)
    assert len(matches) == 1
    assert matches[0].origin == "turn"
    assert matches[0].session_id == "session-a"
    assert "[REDACTED]" in matches[0].content


def test_project_source_log_search_is_scope_isolated(tmp_path: Path) -> None:
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    scope_a = MemoryScope.project(project_a)
    scope_b = MemoryScope.project(project_b)

    store_a = SessionMemoryStore(memory_dir=scope_a.root / scope_a.project_hash, session_id="session-a")
    task_a = _task_with_messages(
        session_id="session-a",
        task_id="task-a",
        query="project alpha decision",
        answer="alpha uses redis queue",
    )
    task_a.session.memory_store = store_a
    store_a.append_turn(task_a)

    store_b = SessionMemoryStore(memory_dir=scope_b.root / scope_b.project_hash, session_id="session-b")
    task_b = _task_with_messages(
        session_id="session-b",
        task_id="task-b",
        query="project beta decision",
        answer="beta uses sqlite queue",
    )
    task_b.session.memory_store = store_b
    store_b.append_turn(task_b)

    matches_a = search_source_logs("redis", scope_a)
    matches_b = search_source_logs("redis", scope_b)

    assert [match.session_id for match in matches_a] == ["session-a"]
    assert matches_b == []


def _task_with_messages(*, session_id: str, task_id: str, query: str, answer: str) -> Task:
    run_params = RunParams(message=query, session_id=session_id, task_id=task_id)
    session = Session(
        session_id=session_id,
        model="",
        provider="",
        context=Context(
            session_id=session_id,
            project_root=Path.cwd(),
            memory_dir=Path.cwd(),
            system_prompt="",
        ),
        current_task_id=task_id,
    )
    session.add_message("user", query)
    session.add_message("assistant", answer, agent_name="llm:test")
    return Task(
        platform="cli",
        session_id=session_id,
        task_id=task_id,
        user_query=query,
        session=session,
        config={},
        run_params=run_params,
        memory_dir=Path.cwd(),
        status="completed",
        output=answer,
    )
