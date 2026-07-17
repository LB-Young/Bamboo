"""Tests for the Bamboo fancy web UI."""

from __future__ import annotations

from fastapi.testclient import TestClient

from bamboo.adapters.web_fancy.app import create_app


def test_fancy_web_index_loads() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Bamboo Fancy Web" in response.text
    assert "Telemetry" in response.text
