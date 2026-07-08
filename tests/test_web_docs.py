"""Tests for the Bamboo web documentation page."""

from __future__ import annotations

from fastapi.testclient import TestClient

from bamboo.adapters.web.app import create_app


def test_docs_route_serves_usage_documentation() -> None:
    client = TestClient(create_app())

    response = client.get("/docs")

    assert response.status_code == 200
    assert "Bamboo 命令使用说明" in response.text
    assert "bamboo web" in response.text
    assert "bamboo docs" in response.text
    assert "--no-browser" in response.text
    assert "bamboo_main_agent.yaml" in response.text
    assert "models.yaml" in response.text
    assert "--session-mode" in response.text
    assert "/api/chat/stream" not in response.text
