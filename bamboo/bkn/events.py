"""BKN event payload helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def topology_event(*, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create an append-only topology event."""
    return {"time": datetime.now(UTC).isoformat(), "action": action, "payload": payload}
