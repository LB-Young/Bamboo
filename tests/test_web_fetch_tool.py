"""web_fetch tool tests."""

from __future__ import annotations

import socket

import httpx
import pytest

from bamboo.tools.buildin.web_fetch import WebFetchTool


@pytest.mark.asyncio
async def test_web_fetch_extracts_html_text(monkeypatch) -> None:
    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><head><style>.x{}</style></head><body><h1>Hello</h1><p>World</p></body></html>",
        )

    result = await WebFetchTool(transport=httpx.MockTransport(handler)).execute("https://example.com", max_length=100)

    assert result.success is True
    assert "Hello" in result.content
    assert "World" in result.content
    assert ".x" not in result.content


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_url() -> None:
    result = await WebFetchTool().execute("http://127.0.0.1:8000")

    assert result.success is False
    assert result.error == "url_blocked"
