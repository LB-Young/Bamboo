"""Tests for the Bamboo web documentation page."""

from __future__ import annotations

from pathlib import Path

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


def test_media_route_serves_local_images_only(tmp_path: Path) -> None:
    client = TestClient(create_app())
    image_path = tmp_path / "result.png"
    text_path = tmp_path / "notes.txt"
    image_path.write_bytes(b"png")
    text_path.write_text("not an image", encoding="utf-8")

    image_response = client.get("/api/media", params={"path": str(image_path)})
    text_response = client.get("/api/media", params={"path": str(text_path)})

    assert image_response.status_code == 200
    assert image_response.content == b"png"
    assert text_response.status_code == 400
