"""Debug script: start Bamboo's interactive CLI session.

Use this when you want to debug multi-turn terminal behavior. The process will
wait for input in the VS Code integrated terminal. Type /exit to stop.

This script uses the real user config under ~/.bamboo and may call the configured LLM.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bamboo.helpers.constant import SessionMode  # noqa: E402
from bamboo.run import main  # noqa: E402


def run() -> None:
    """Start the interactive CLI loop."""
    main(
        message=None,
        project=PROJECT_ROOT,
        model=None,
        provider=None,
        permission="default",
        no_stream=False,
        yes_all=False,
        debug_events=True,
        session_mode=SessionMode.project,
        resume=None,
        record_dir=None,
    )


if __name__ == "__main__":
    run()
