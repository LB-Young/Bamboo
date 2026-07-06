"""Eval runner tests."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest
import yaml
from typer.testing import CliRunner

from bamboo.eval import EvalRunner, export_replay_case, load_eval_case
from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
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


def test_replay_eval_case_runs_without_model(tmp_path: Path) -> None:
    record_dir = _create_session_record(session_id="session-eval", answer="done")
    case_dir = tmp_path / "case"
    _write_case(
        case_dir,
        input_data={"mode": "replay", "fixture": str(record_dir)},
        expected_data={
            "status": "passed",
            "min_events": 2,
            "min_turns": 1,
            "min_messages": 2,
            "event_types": ["task-create", "step-finish"],
            "output_contains": ["done"],
            "max_errors": 0,
        },
    )

    async def run_test():
        return await EvalRunner().run_case(load_eval_case(case_dir))

    report = anyio.run(run_test)

    assert report.passed
    assert report.mode == "replay"
    assert report.summary["events"] == 2


def test_live_eval_case_uses_runtime_factory(tmp_path: Path) -> None:
    case_dir = tmp_path / "live-case"
    _write_case(
        case_dir,
        input_data={"mode": "live", "message": "say hi", "session_mode": "chat"},
        expected_data={
            "status": "passed",
            "final_task_status": "completed",
            "min_turns": 1,
            "output_contains": ["hi from eval"],
        },
    )

    async def run_test():
        return await EvalRunner(runtime_factory=lambda: _LiveRuntime()).run_case(load_eval_case(case_dir))

    report = anyio.run(run_test)

    assert report.passed
    assert report.output == "hi from eval"


def test_export_replay_case_copies_session_fixture(tmp_path: Path) -> None:
    _create_session_record(session_id="session-export", answer="exported")
    case = export_replay_case(session_id="session-export", case_dir=tmp_path / "exported")

    assert (case.case_dir / "fixtures" / "session" / "session.json").is_file()
    assert case.input.mode == "replay"
    assert case.expected.min_turns == 1


def test_eval_run_cli_prints_report(tmp_path: Path) -> None:
    record_dir = _create_session_record(session_id="session-cli", answer="cli answer")
    case_dir = tmp_path / "cli-case"
    _write_case(
        case_dir,
        input_data={"mode": "replay", "fixture": str(record_dir)},
        expected_data={"status": "passed", "output_contains": ["cli answer"]},
    )

    result = CliRunner().invoke(app, ["eval", "run", str(case_dir)])

    assert result.exit_code == 0
    assert "PASS cli-case mode=replay" in result.output


def _write_case(case_dir: Path, *, input_data: dict, expected_data: dict) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "input.yaml").write_text(yaml.safe_dump(input_data, sort_keys=False), encoding="utf-8")
    (case_dir / "expected.yaml").write_text(yaml.safe_dump(expected_data, sort_keys=False), encoding="utf-8")


def _create_session_record(*, session_id: str, answer: str) -> Path:
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
    store._append_jsonl(
        record_dir / "messages.jsonl",
        {
            "role": "user",
            "content": "hello",
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
    store._append_jsonl(record_dir / "events.jsonl", {"type": "step-finish", "session_id": session_id, "task_id": "task"})
    store._append_jsonl(record_dir / "tasks.jsonl", {"status": "completed", "task_id": "task"})
    store._append_jsonl(
        record_dir / "turns.jsonl",
        {"task_id": "task", "status": "completed", "user_message": "hello", "assistant_answer": answer, "error": ""},
    )
    return record_dir


class _LiveRuntime:
    async def run(self, run_params: RunParams) -> Task:
        session = Session(
            session_id=run_params.session_id,
            model=run_params.model,
            provider=run_params.provider,
            context=Context(
                session_id=run_params.session_id,
                project_root=Path(run_params.project),
                memory_dir=Path.cwd(),
                system_prompt="system",
                metadata={"prompt_mode": "chat"},
            ),
        )
        session.add_message("user", run_params.message)
        task = Task(
            platform="eval",
            session_id=run_params.session_id,
            task_id=run_params.task_id,
            user_query=run_params.message,
            session=session,
            config={},
            run_params=run_params,
            memory_dir=Path.cwd(),
            status="completed",
            output="hi from eval",
        )
        return task
