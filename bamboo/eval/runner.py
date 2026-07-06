"""Evaluation runner for replay and live cases."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from bamboo.eval.case import EvalCase, session_mode_value
from bamboo.eval.report import EvalCheck, EvalReport
from bamboo.helpers.requests_params import RunParams
from bamboo.memory.session_store import build_replay_summary
from bamboo.runtime import TaskRuntime

RuntimeFactory = Callable[[], TaskRuntime]


class EvalRunner:
    """Run replay or live eval cases and produce structured reports."""

    def __init__(self, *, runtime_factory: RuntimeFactory | None = None) -> None:
        self.runtime_factory = runtime_factory or TaskRuntime

    async def run_case(self, case: EvalCase) -> EvalReport:
        """Run one eval case."""
        if case.input.mode == "live":
            return await self._run_live(case)
        return self._run_replay(case)

    def _run_replay(self, case: EvalCase) -> EvalReport:
        record_dir = _resolve_replay_record_dir(case)
        summary = build_replay_summary(record_dir)
        output = "\n".join(str(turn.get("assistant_answer") or "") for turn in summary["turns"])
        checks = _evaluate_summary(case, summary=summary, output=output)
        return EvalReport(
            case_name=case.name,
            mode="replay",
            passed=all(check.passed for check in checks),
            checks=tuple(checks),
            summary=_summary_counts(summary),
            record_dir=str(record_dir),
            output=output,
        )

    async def _run_live(self, case: EvalCase) -> EvalReport:
        if not case.input.message.strip():
            raise ValueError("live eval case requires input.message")
        runtime = self.runtime_factory()
        run_params = RunParams(
            platform="eval",
            message=case.input.message,
            project=case.input.project or str(case.case_dir),
            model=case.input.model,
            provider=case.input.provider,
            permission=case.input.permission,
            no_stream=case.input.no_stream,
            yes_all=case.input.yes_all,
            debug_events=case.input.debug_events,
            session_mode=session_mode_value(case.input.session_mode),
            task_id=str(uuid4()),
            session_id=case.input.session_id or str(uuid4()),
        )
        task = await runtime.run(run_params)
        record_dir = ""
        summary = _live_summary(task)
        if task.session.memory_store is not None:
            record_dir = str(task.session.memory_store.session_dir)
            summary = build_replay_summary(task.session.memory_store.session_dir)
        output = task.output or "\n".join(str(turn.get("assistant_answer") or "") for turn in summary["turns"])
        checks = _evaluate_summary(case, summary=summary, output=output)
        if case.expected.final_task_status:
            checks.append(
                EvalCheck(
                    name="final_task_status",
                    passed=task.status == case.expected.final_task_status,
                    expected=case.expected.final_task_status,
                    actual=task.status,
                )
            )
        return EvalReport(
            case_name=case.name,
            mode="live",
            passed=all(check.passed for check in checks),
            checks=tuple(checks),
            summary=_summary_counts(summary),
            record_dir=record_dir,
            output=output,
        )


def _resolve_replay_record_dir(case: EvalCase) -> Path:
    if case.input.record_dir:
        candidate = Path(case.input.record_dir).expanduser()
        if not candidate.is_absolute():
            candidate = case.case_dir / candidate
        return candidate.resolve(strict=False)
    fixture = Path(case.input.fixture)
    if not fixture.is_absolute():
        fixture = case.case_dir / fixture
    if fixture.is_dir():
        return fixture.resolve(strict=False)
    raise ValueError("replay eval case requires input.record_dir or an existing fixture directory")


def _evaluate_summary(case: EvalCase, *, summary: dict, output: str) -> list[EvalCheck]:
    expected = case.expected
    checks = [
        EvalCheck(
            name="min_events",
            passed=int(summary["event_count"]) >= expected.min_events,
            expected=expected.min_events,
            actual=summary["event_count"],
        ),
        EvalCheck(
            name="min_turns",
            passed=int(summary["turn_count"]) >= expected.min_turns,
            expected=expected.min_turns,
            actual=summary["turn_count"],
        ),
        EvalCheck(
            name="min_messages",
            passed=int(summary["message_count"]) >= expected.min_messages,
            expected=expected.min_messages,
            actual=summary["message_count"],
        ),
    ]
    event_types = [str(event.get("type") or "") for event in summary["events"]]
    for event_type in expected.event_types:
        checks.append(
            EvalCheck(
                name=f"event_type:{event_type}",
                passed=event_type in event_types,
                expected=event_type,
                actual=event_types,
            )
        )
    for needle in expected.output_contains:
        checks.append(
            EvalCheck(
                name=f"output_contains:{needle}",
                passed=needle in output,
                expected=needle,
                actual=output,
            )
        )
    if expected.max_errors is not None:
        error_count = _error_count(summary)
        checks.append(
            EvalCheck(
                name="max_errors",
                passed=error_count <= expected.max_errors,
                expected=expected.max_errors,
                actual=error_count,
            )
        )
    expected_status = expected.status.lower()
    if expected_status in {"passed", "failed"}:
        will_pass = all(check.passed for check in checks)
        checks.append(
            EvalCheck(
                name="status",
                passed=(will_pass and expected_status == "passed") or (not will_pass and expected_status == "failed"),
                expected=expected_status,
                actual="passed" if will_pass else "failed",
            )
        )
    return checks


def _live_summary(task) -> dict:
    return {
        "session": {},
        "record_dir": "",
        "message_count": len(getattr(task.session, "messages", []) or []),
        "event_count": 0,
        "task_count": 1,
        "turn_count": 1,
        "llm_request_count": 0,
        "llm_response_count": 0,
        "tool_call_count": 0,
        "tool_result_count": 0,
        "messages": [],
        "events": [],
        "tasks": [{"status": getattr(task, "status", "")}],
        "turns": [
            {
                "task_id": getattr(task, "task_id", ""),
                "status": getattr(task, "status", ""),
                "user_message": getattr(task, "user_query", ""),
                "assistant_answer": getattr(task, "output", ""),
                "error": getattr(task, "error", ""),
            }
        ],
    }


def _summary_counts(summary: dict) -> dict[str, int]:
    return {
        "messages": int(summary["message_count"]),
        "events": int(summary["event_count"]),
        "tasks": int(summary["task_count"]),
        "turns": int(summary["turn_count"]),
        "llm": int(summary["llm_request_count"]),
        "tools": int(summary["tool_call_count"]),
    }


def _error_count(summary: dict) -> int:
    events = summary["events"]
    turns = summary["turns"]
    tasks = summary["tasks"]
    event_errors = sum(1 for event in events if "error" in str(event.get("type") or "") or event.get("error"))
    turn_errors = sum(1 for turn in turns if turn.get("error"))
    task_errors = sum(1 for task in tasks if task.get("status") == "failed" or task.get("error"))
    return event_errors + turn_errors + task_errors
