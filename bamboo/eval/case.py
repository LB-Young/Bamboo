"""Evaluation case loading and fixture export."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from bamboo.helpers.constant import SessionMode
from bamboo.memory.session_store import find_session_record

EvalMode = Literal["replay", "live"]


@dataclass(frozen=True, slots=True)
class EvalCaseInput:
    """Input side of an eval case."""

    mode: EvalMode = "replay"
    session_id: str = ""
    record_dir: str = ""
    fixture: str = "fixtures/session"
    message: str = ""
    project: str = ""
    model: str = ""
    provider: str = ""
    permission: str = "default"
    session_mode: str = "chat"
    yes_all: bool = False
    no_stream: bool = False
    debug_events: bool = False


@dataclass(frozen=True, slots=True)
class EvalExpected:
    """Expected assertions for an eval case."""

    status: str = "passed"
    final_task_status: str = ""
    output_contains: tuple[str, ...] = ()
    event_types: tuple[str, ...] = ()
    min_events: int = 0
    min_turns: int = 0
    min_messages: int = 0
    max_errors: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvalCase:
    """A loaded eval case directory."""

    name: str
    case_dir: Path
    input: EvalCaseInput
    expected: EvalExpected


def load_eval_case(case_dir: Path | str) -> EvalCase:
    """Load input.yaml and expected.yaml from a case directory."""
    root = Path(case_dir).expanduser().resolve(strict=False)
    input_path = root / "input.yaml"
    expected_path = root / "expected.yaml"
    if not input_path.is_file():
        raise ValueError(f"eval case missing input.yaml: {root}")
    if not expected_path.is_file():
        raise ValueError(f"eval case missing expected.yaml: {root}")
    return EvalCase(
        name=root.name,
        case_dir=root,
        input=_parse_input(_read_yaml_mapping(input_path), root),
        expected=_parse_expected(_read_yaml_mapping(expected_path)),
    )


def export_replay_case(
    *,
    session_id: str,
    case_dir: Path | str,
    mode: str = "auto",
    project_path: Path | None = None,
    record_dir: Path | str | None = None,
    memory_root: Path | None = None,
    overwrite: bool = False,
) -> EvalCase:
    """Export one persisted session record as a replay eval fixture."""
    target = Path(case_dir).expanduser().resolve(strict=False)
    if target.exists() and any(target.iterdir()) and not overwrite:
        raise ValueError(f"eval case already exists: {target}")
    resolved = find_session_record(
        session_id,
        mode=mode,
        project_path=project_path,
        record_dir=record_dir,
        memory_root=memory_root,
    )
    if resolved is None:
        raise ValueError(f"session not found: {session_id}")
    fixture_dir = target / "fixtures" / "session"
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    fixture_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(resolved, fixture_dir)
    (target / "input.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "replay",
                "session_id": session_id,
                "fixture": "fixtures/session",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    summary = _fixture_summary(fixture_dir)
    (target / "expected.yaml").write_text(
        yaml.safe_dump(
            {
                "status": "passed",
                "min_events": summary["event_count"],
                "min_turns": summary["turn_count"],
                "min_messages": summary["message_count"],
                "event_types": summary["event_types"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return load_eval_case(target)


def _parse_input(raw: dict[str, Any], case_dir: Path) -> EvalCaseInput:
    mode = str(raw.get("mode") or "replay").strip().lower()
    if mode not in {"replay", "live"}:
        raise ValueError("eval input mode must be replay/live")
    session_mode = str(raw.get("session_mode") or "chat").strip().lower()
    if session_mode not in {"auto", "chat", "project"}:
        raise ValueError("eval input session_mode must be auto/chat/project")
    return EvalCaseInput(
        mode=mode,  # type: ignore[arg-type]
        session_id=str(raw.get("session_id") or ""),
        record_dir=str(raw.get("record_dir") or ""),
        fixture=str(raw.get("fixture") or "fixtures/session"),
        message=str(raw.get("message") or ""),
        project=str(raw.get("project") or case_dir),
        model=str(raw.get("model") or ""),
        provider=str(raw.get("provider") or ""),
        permission=str(raw.get("permission") or "default"),
        session_mode=session_mode,
        yes_all=bool(raw.get("yes_all", False)),
        no_stream=bool(raw.get("no_stream", False)),
        debug_events=bool(raw.get("debug_events", False)),
    )


def _parse_expected(raw: dict[str, Any]) -> EvalExpected:
    max_errors = raw.get("max_errors")
    if max_errors is not None and (not isinstance(max_errors, int) or max_errors < 0):
        raise ValueError("expected.max_errors must be a non-negative integer")
    return EvalExpected(
        status=str(raw.get("status") or "passed"),
        final_task_status=str(raw.get("final_task_status") or ""),
        output_contains=tuple(str(item) for item in raw.get("output_contains", []) or []),
        event_types=tuple(str(item) for item in raw.get("event_types", []) or []),
        min_events=_non_negative_int(raw.get("min_events", 0), "min_events"),
        min_turns=_non_negative_int(raw.get("min_turns", 0), "min_turns"),
        min_messages=_non_negative_int(raw.get("min_messages", 0), "min_messages"),
        max_errors=max_errors,
        metadata={str(key): item for key, item in raw.items() if key not in _EXPECTED_FIELDS},
    )


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"YAML file must contain a mapping: {path}")
    return raw


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"expected.{field_name} must be a non-negative integer")
    return value


def _fixture_summary(record_dir: Path) -> dict[str, Any]:
    import json

    def read_jsonl(name: str) -> list[dict[str, Any]]:
        path = record_dir / name
        if not path.is_file():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        return rows

    events = read_jsonl("events.jsonl")
    return {
        "event_count": len(events),
        "turn_count": len(read_jsonl("turns.jsonl")),
        "message_count": len(read_jsonl("messages.jsonl")),
        "event_types": sorted({str(event.get("type") or "") for event in events if event.get("type")}),
    }


_EXPECTED_FIELDS = {
    "status",
    "final_task_status",
    "output_contains",
    "event_types",
    "min_events",
    "min_turns",
    "min_messages",
    "max_errors",
}


def session_mode_value(value: str) -> SessionMode:
    """Convert a case session_mode value to RunParams SessionMode."""
    if value == "project":
        return SessionMode.project
    if value == "auto":
        return SessionMode.auto
    return SessionMode.chat
