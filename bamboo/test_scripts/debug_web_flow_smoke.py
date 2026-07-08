"""Debug script: exercise Web endpoints without starting a network server.

This is useful for breakpoints in FastAPI handlers and session listing code.
By default it only calls cheap endpoints and does not invoke the LLM.

Set BAMBOO_DEBUG_WEB_LIVE_STREAM=1 to also POST /api/chat/stream. That path may
call the configured LLM and produce API cost.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bamboo.adapters.web.app import create_app  # noqa: E402


def run() -> None:
    """Call Web endpoints through TestClient."""
    client = TestClient(create_app())

    health = client.get("/api/health")
    print("GET /api/health", health.status_code, health.json())

    docs = client.get("/docs")
    print("GET /docs", docs.status_code, "Bamboo 命令使用说明" in docs.text)

    sidebar = client.get("/api/sidebar", params={"mode": "project", "project_path": str(PROJECT_ROOT)})
    print("GET /api/sidebar", sidebar.status_code, sidebar.json().keys())

    if os.environ.get("BAMBOO_DEBUG_WEB_LIVE_STREAM") != "1":
        print("skip POST /api/chat/stream; set BAMBOO_DEBUG_WEB_LIVE_STREAM=1 to run it")
        return

    with client.stream(
        "POST",
        "/api/chat/stream",
        json={
            "message": "请用一句话说明 Bamboo Web 调试链路。",
            "mode": "project",
            "project_path": str(PROJECT_ROOT),
            "debug_events": True,
        },
    ) as response:
        print("POST /api/chat/stream", response.status_code)
        for line in response.iter_lines():
            if line:
                print(line)


if __name__ == "__main__":
    run()
