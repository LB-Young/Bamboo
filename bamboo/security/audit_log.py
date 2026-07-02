"""JSONL audit logging for tool calls and permission decisions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bamboo.userspace.userspace import get_userspace_dir


SENSITIVE_KEYS = {"api_key", "apikey", "token", "authorization", "password", "secret"}
MAX_PREVIEW_CHARS = 2000


@dataclass(slots=True)
class ToolAuditRecord:
    """One audit record for a tool call."""

    session_id: str
    task_id: str
    tool_call_id: str
    tool_name: str
    risk_level: str
    decision: str
    approved: bool
    reason: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    success: bool | None = None
    error: str = ""
    duration_ms: int | None = None
    output_preview: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class ToolAuditLogger:
    """Append-only JSONL audit writer."""

    def __init__(self, path: Path | str | None = None, *, enabled: bool = True) -> None:
        """Create an audit logger.

        Write errors are swallowed because audit logging should not crash agent
        execution in restricted test environments.
        """
        self.path = Path(path) if path is not None else get_userspace_dir() / "storage" / "audit" / "tool_calls.jsonl"
        self.enabled = enabled

    def append(self, record: ToolAuditRecord) -> None:
        """Append a redacted record to the audit log."""
        if not self.enabled:
            return
        payload = asdict(record)
        payload["arguments"] = redact_sensitive(payload.get("arguments", {}))
        payload["output_preview"] = _preview(str(payload.get("output_preview", "")))
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError:
            return


def redact_sensitive(value: Any) -> Any:
    """Redact sensitive keys recursively from JSON-like values."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def _preview(content: str) -> str:
    if len(content) <= MAX_PREVIEW_CHARS:
        return content
    return content[:MAX_PREVIEW_CHARS] + "\n[preview truncated]"
