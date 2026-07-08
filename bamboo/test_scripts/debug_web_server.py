"""Debug script: start Bamboo Web and open the browser.

Use this when you want to debug the real Web UI flow:
    bamboo/run.py -> bamboo.adapters.web.app -> TaskRuntime -> AgentRuntime

Open http://127.0.0.1:8899 after launch if the browser does not open automatically.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bamboo.run import web  # noqa: E402


def run() -> None:
    """Start the Web server on the default development port."""
    web(host="127.0.0.1", port=8899, reload=False, no_browser=False)


if __name__ == "__main__":
    run()
