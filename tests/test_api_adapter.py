"""Tests for the platform-neutral HTTP API adapter."""

from __future__ import annotations

from fastapi.testclient import TestClient

from bamboo.adapters.api.app import ApiChatRequest, _images_from_payload, create_app


def test_api_health_route() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_images_merge_explicit_fields_and_message_text() -> None:
    payload = ApiChatRequest(
        message="describe https://example.com/a.png",
        images=["https://example.com/explicit.webp"],
        image_paths=["/tmp/local.jpg"],
    )

    images = _images_from_payload(payload)

    assert [image.source for image in images] == [
        "https://example.com/explicit.webp",
        "/tmp/local.jpg",
        "https://example.com/a.png",
    ]
