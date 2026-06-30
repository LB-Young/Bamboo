"""Session listing and restore helpers for the Bamboo web UI."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from bamboo.factory.context import Context
from bamboo.factory.message import Message
from bamboo.factory.session import Session
from bamboo.memory.get_memory_path import get_memory_dir, get_memory_dir_name
from bamboo.memory.session_store import SessionMemoryStore


def list_sessions(*, mode: str, project_path: Path | None = None, limit: int = 40) -> list[dict[str, Any]]:
    """List persisted sessions for the selected web mode."""
    memory_root = get_memory_dir()
    bases: list[Path]
    if mode == "project" and project_path is not None:
        bases = [memory_root / "projects" / get_memory_dir_name(project_path)]
    else:
        bases = sorted((memory_root / "dates").glob("*"), reverse=True) if (memory_root / "dates").exists() else []

    rows: list[dict[str, Any]] = []
    for base in bases:
        rows.extend(_list_session_records(base, project_path=project_path if mode == "project" else None))
        if len(rows) >= limit:
            break
    rows.sort(key=lambda row: row.get("updated_at") or row.get("created_at") or "", reverse=True)
    return rows[:limit]


def resolve_session_record(
    session_id: str,
    *,
    mode: str,
    project_path: Path | None = None,
    record_dir: str | None = None,
) -> Path | None:
    """Resolve a persisted session directory."""
    if record_dir:
        candidate = Path(record_dir).expanduser()
        if _is_session_record(candidate, session_id=session_id):
            return candidate

    for row in list_sessions(mode=mode, project_path=project_path, limit=200):
        if row.get("session_id") != session_id:
            continue
        candidate = Path(str(row.get("record_dir", ""))).expanduser()
        if _is_session_record(candidate, session_id=session_id):
            return candidate
    return None


def load_session(record_dir: Path) -> Session:
    """Restore a Session object from a Bamboo memory record directory."""
    meta = _read_json(record_dir / "session.json") or {}
    session_id = str(meta.get("session_id") or record_dir.name)
    memory_dir = Path(str(meta.get("memory_dir") or record_dir.parent)).expanduser()
    project_root = Path(str(meta.get("project_root") or Path.cwd())).expanduser()
    system_prompt = _read_text(record_dir / "system_prompt.md")

    context = Context(
        session_id=session_id,
        project_root=project_root,
        memory_dir=memory_dir,
        system_prompt=system_prompt,
        metadata=dict(meta.get("metadata") or {}),
    )
    store = SessionMemoryStore(memory_dir=memory_dir, session_id=session_id, record_dir=record_dir)
    session = Session(
        session_id=session_id,
        model=str(meta.get("model") or ""),
        provider=str(meta.get("provider") or ""),
        context=context,
        memory_store=store,
    )
    session.messages = _load_messages(record_dir / "messages.jsonl")
    return session


def serialize_messages(session: Session) -> list[dict[str, str]]:
    """Return displayable chat messages."""
    rows: list[dict[str, str]] = []
    for message in session.messages:
        if message.role not in {"user", "assistant", "tool"}:
            continue
        if message.compressed or not message.content.strip():
            continue
        role = message.role if message.role in {"user", "assistant"} else "tool"
        rows.append({"role": role, "content": message.content, "time": message.created_at})
    return rows


def _list_session_records(base: Path, *, project_path: Path | None) -> list[dict[str, Any]]:
    if not base.exists():
        return []

    candidates = [base] if (base / "session.json").is_file() else []
    candidates.extend(path for path in base.iterdir() if path.is_dir() and (path / "session.json").is_file())

    rows: list[dict[str, Any]] = []
    for record in candidates:
        meta = _read_json(record / "session.json")
        if not meta:
            continue
        if project_path is not None:
            saved_project = Path(str(meta.get("project_root") or "")).expanduser().resolve(strict=False)
            requested_project = project_path.expanduser().resolve(strict=False)
            if saved_project != requested_project:
                continue
        session_id = str(meta.get("session_id") or record.name)
        created_at = str(meta.get("created_at") or "")
        updated_at = str(meta.get("updated_at") or created_at)
        rows.append(
            {
                "session_id": session_id,
                "mode": str(meta.get("mode") or ""),
                "label": _session_label(record, fallback=session_id),
                "created_at": created_at,
                "updated_at": updated_at,
                "record_dir": str(record),
                "project_root": str(meta.get("project_root") or ""),
            }
        )
    return rows


def _session_label(record_dir: Path, *, fallback: str) -> str:
    for payload in _read_jsonl(record_dir / "messages.jsonl"):
        if payload.get("role") == "user":
            text = str(payload.get("content") or "").strip()
            if text:
                return text[:72]
    return fallback


def _load_messages(path: Path) -> list[Message]:
    messages: list[Message] = []
    for payload in _read_jsonl(path):
        role = payload.get("role")
        content = payload.get("content")
        if role not in {"system", "user", "assistant", "tool"} or not isinstance(content, str):
            continue
        messages.append(
            Message(
                role=role,
                content=content,
                agent_name=str(payload.get("agent_name") or ""),
                message_id=str(payload.get("message_id") or ""),
                created_at=str(payload.get("time") or payload.get("created_at") or datetime.now().isoformat()),
                message_type=str(payload.get("message_type") or "normal"),
                active_for_prompt=bool(payload.get("active_for_prompt", True)),
                compressed=bool(payload.get("compressed", False)),
                origin_message_ids=list(payload.get("origin_message_ids") or []),
                metadata=dict(payload.get("metadata") or {}),
                tool_calls=list(payload.get("tool_calls") or []),
                tool_call_id=str(payload.get("tool_call_id") or ""),
                tool_name=str(payload.get("tool_name") or ""),
            )
        )
    return messages


def _is_session_record(path: Path, *, session_id: str) -> bool:
    meta = _read_json(path / "session.json")
    return bool(meta and meta.get("session_id") == session_id and (path / "messages.jsonl").exists())


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""

