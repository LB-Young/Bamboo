"""Debug script: run one Bamboo CLI turn through the normal main command path.

Use this when you want breakpoints in:
    bamboo/run.py
    bamboo/adapters/cli/main.py
    bamboo/runtime/task_runtime.py
    bamboo/runtime/agent_runtime.py

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
    """Run one non-interactive CLI turn."""
    main(
        message="请用一句话说明当前 Bamboo 项目的主要功能。",
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
