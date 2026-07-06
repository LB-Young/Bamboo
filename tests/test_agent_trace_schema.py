"""Agent trace schema documentation tests."""

from __future__ import annotations

import inspect
import re
from dataclasses import is_dataclass
from pathlib import Path
from typing import get_args

from bamboo.helpers import constant
from bamboo.helpers.constant import BambooEvent
from bamboo.helpers.utils import BaseEvent


DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "agent-trace-events.md"
COMMON_FIELDS = {
    "type",
    "session_id",
    "timestamp",
    "event_id",
    "parent_event_id",
    "step_id",
    "task_id",
    "plat_info",
}


def test_agent_trace_schema_doc_lists_every_event_type_and_field() -> None:
    documented = _documented_event_schema()
    actual = _actual_event_schema()

    assert documented.keys() == actual.keys()
    for event_type, schema in actual.items():
        assert documented[event_type]["class"] == schema["class"]
        assert documented[event_type]["fields"] == schema["fields"]


def test_all_events_to_dict_include_common_trace_fields() -> None:
    for event_type, schema in _actual_event_schema().items():
        missing = COMMON_FIELDS - set(schema["fields"])
        assert not missing, f"{event_type} missing common fields: {sorted(missing)}"


def test_bamboo_event_union_includes_every_documented_event_class() -> None:
    union_classes = set(_flatten_union_args(BambooEvent))
    event_classes = {schema["class_obj"] for schema in _actual_event_schema().values()}
    assert event_classes <= union_classes


def test_agent_trace_doc_mentions_pattern_compatibility() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "`tool.*` 可以匹配 `tool-call`" in content
    assert "`event.to_dict()`" in content


def _actual_event_schema() -> dict[str, dict]:
    schemas: dict[str, dict] = {}
    for name, obj in vars(constant).items():
        if not _is_event_class(name, obj):
            continue
        event = obj(session_id="session-schema", task_id="task-schema")
        payload = event.to_dict()
        event_type = payload["type"]
        schemas[event_type] = {
            "class": name,
            "class_obj": obj,
            "fields": list(payload.keys()),
        }
    return dict(sorted(schemas.items()))


def _documented_event_schema() -> dict[str, dict]:
    content = DOC_PATH.read_text(encoding="utf-8")
    rows: dict[str, dict] = {}
    pattern = re.compile(r"^\| `([^`]+)` \| `([^`]+)` \| ([^|]+) \| `([^`]+)` \|$", re.MULTILINE)
    for event_type, class_name, _category, fields in pattern.findall(content):
        if event_type == "Type":
            continue
        rows[event_type] = {
            "class": class_name,
            "fields": [field.strip() for field in fields.split(",")],
        }
    return dict(sorted(rows.items()))


def _is_event_class(name: str, value: object) -> bool:
    return (
        inspect.isclass(value)
        and name.endswith("Event")
        and issubclass(value, BaseEvent)
        and value is not BaseEvent
        and is_dataclass(value)
    )


def _flatten_union_args(value: object) -> tuple[type, ...]:
    args = get_args(value)
    if not args:
        return (value,) if inspect.isclass(value) else ()
    flattened: list[type] = []
    for item in args:
        flattened.extend(_flatten_union_args(item))
    return tuple(flattened)
