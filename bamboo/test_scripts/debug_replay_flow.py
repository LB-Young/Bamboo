"""Debug script: inspect replay session discovery and replay selection.

This does not call the LLM. It lists persisted sessions, then replays the latest
session if one exists.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bamboo.helpers.constant import SessionMode  # noqa: E402
from bamboo.memory.session_store import list_session_records  # noqa: E402
from bamboo.run import replay  # noqa: E402


def run() -> None:
    """List sessions and replay the latest one."""
    replay(
        session_id="list",
        mode=SessionMode.auto,
        project=None,
        record_dir=None,
        json_output=False,
        limit=10,
    )
    if not list_session_records(mode=SessionMode.auto.value, limit=1):
        print("No persisted sessions found; run a Bamboo task first.")
        return
    replay(
        session_id="latest",
        mode=SessionMode.auto,
        project=None,
        record_dir=None,
        json_output=False,
        limit=10,
    )


if __name__ == "__main__":
    run()
