"""Search full-fidelity memory source logs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bamboo.helpers.redact import redact_sensitive_text
from bamboo.memory.scope import MemoryScope


@dataclass(frozen=True, slots=True)
class SourceLogMatch:
    """One source-log search hit."""

    session_id: str
    task_id: str
    source: str
    content: str
    score: int
    origin: str


def search_source_logs(query: str, scope: MemoryScope, *, limit: int = 10) -> list[SourceLogMatch]:
    """Search source turns first, then raw messages as a fallback."""
    terms = _terms(query)
    if not terms or not scope.root.exists():
        return []
    matches = _search_jsonl_files(scope.root.rglob("turns.jsonl"), terms, origin="turn")
    if not matches:
        matches = _search_jsonl_files(scope.root.rglob("messages.jsonl"), terms, origin="message")
    return sorted(matches, key=lambda match: match.score, reverse=True)[:limit]


def _search_jsonl_files(paths: Any, terms: set[str], *, origin: str) -> list[SourceLogMatch]:
    matches: list[SourceLogMatch] = []
    for path in paths:
        for record in _read_jsonl(path):
            content = _render_record(record)
            score = _score(content, terms)
            if score <= 0:
                continue
            matches.append(
                SourceLogMatch(
                    session_id=str(record.get("session_id", "")),
                    task_id=str(record.get("task_id", "")),
                    source=str(path),
                    content=redact_sensitive_text(content),
                    score=score,
                    origin=origin,
                )
            )
    return matches


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return records
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _render_record(record: dict[str, Any]) -> str:
    if record.get("type") == "turn":
        parts = [str(record.get("user_message", "")), str(record.get("assistant_answer", ""))]
        for tool_call in record.get("tool_calls", []) or []:
            if isinstance(tool_call, dict):
                parts.append(str(tool_call.get("name", "")))
                parts.append(json.dumps(tool_call.get("arguments", {}), ensure_ascii=False, sort_keys=True))
        for tool_result in record.get("tool_results", []) or []:
            if isinstance(tool_result, dict):
                parts.append(str(tool_result.get("tool_name", "")))
                parts.append(str(tool_result.get("summary", "")))
        return "\n".join(part for part in parts if part)
    return str(record.get("content", ""))


def _terms(query: str) -> set[str]:
    return {part.lower() for part in query.split() if part.strip()}


def _score(content: str, terms: set[str]) -> int:
    normalized = content.lower()
    return sum(normalized.count(term) for term in terms)
