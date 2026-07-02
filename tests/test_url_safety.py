"""URL safety tests."""

from __future__ import annotations

import socket

from bamboo.security.url_safety import is_url_allowed


def test_url_safety_blocks_localhost() -> None:
    allowed, reason = is_url_allowed("http://localhost:8000")
    assert allowed is False
    assert "blocked hostname" in reason


def test_url_safety_blocks_private_ip() -> None:
    allowed, reason = is_url_allowed("http://192.168.1.10")
    assert allowed is False
    assert "blocked non-public IP" in reason


def test_url_safety_blocks_metadata_ip() -> None:
    allowed, reason = is_url_allowed("http://169.254.169.254/latest/meta-data")
    assert allowed is False
    assert "metadata" in reason


def test_url_safety_allows_public_url(monkeypatch) -> None:
    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    allowed, reason = is_url_allowed("https://example.com")
    assert allowed is True
    assert reason == "allowed"
