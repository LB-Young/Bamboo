"""Session listing and restore helpers for the Bamboo web UI."""

from __future__ import annotations

from pathlib import Path

from bamboo.factory.session import Session
from bamboo.memory.session_store import find_session_record, list_session_records, load_session_record


def list_sessions(*, mode: str, project_path: Path | None = None, limit: int = 40) -> list[dict[str, str]]:
    """List persisted sessions for the selected web mode."""
    records = list_session_records(
        mode=mode,
        project_path=project_path if mode == "project" else None,
        limit=limit,
    )
    return [
        {
            "session_id": record.session_id,
            "mode": record.mode,
            "label": record.label,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "record_dir": str(record.record_dir),
            "project_root": str(record.project_root),
        }
        for record in records
    ]


def resolve_session_record(
    session_id: str,
    *,
    mode: str,
    project_path: Path | None = None,
    record_dir: str | None = None,
) -> Path | None:
    """Resolve a persisted session directory."""
    return find_session_record(
        session_id,
        mode=mode,
        project_path=project_path if mode == "project" else None,
        record_dir=record_dir,
    )


def load_session(record_dir: Path) -> Session:
    """Restore a Session object from a Bamboo memory record directory."""
    return load_session_record(record_dir)


def serialize_messages(session: Session) -> list[dict[str, object]]:
    """Return displayable chat messages."""
    rows: list[dict[str, object]] = []
    for message in session.messages:
        if message.role not in {"user", "assistant"}:
            continue
        if message.compressed or (not message.content.strip() and not message.images):
            continue
        rows.append(
            {
                "role": message.role,
                "content": message.content,
                "time": message.created_at,
                "metadata": dict(message.metadata),
                "images": [
                    {"source": image.source, "media_type": image.media_type, "detail": image.detail}
                    for image in message.images
                ],
            }
        )
    return rows
