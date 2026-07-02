"""Safe web page fetching tool."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

import httpx

from bamboo.security.url_safety import is_url_allowed
from bamboo.tools.buildin.base import Tool, ToolResult


DEFAULT_MAX_LENGTH = 12000
MAX_ALLOWED_LENGTH = 100000


class WebFetchTool(Tool):
    """Fetch a public HTTP(S) URL and return readable text."""

    name = "web_fetch"
    description = "Fetch a public HTTP(S) URL with SSRF protections and return extracted text."
    risk_level = "network"
    tags = ("web", "network", "read")

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 15.0) -> None:
        self.transport = transport
        self.timeout = timeout

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Public HTTP(S) URL to fetch."},
                "max_length": {"type": "integer", "description": "Maximum returned characters."},
            },
            "required": ["url"],
        }

    async def execute(self, url: str, max_length: int = DEFAULT_MAX_LENGTH) -> ToolResult:
        allowed, reason = is_url_allowed(url)
        if not allowed:
            return ToolResult(content=f"URL blocked: {reason}", success=False, error="url_blocked")

        limit = max(1, min(max_length or DEFAULT_MAX_LENGTH, MAX_ALLOWED_LENGTH))
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                return ToolResult(content=f"Fetch failed: {exc}", success=False, error="fetch_failed")

        content_type = response.headers.get("content-type", "")
        raw_text = response.text
        text = _html_to_text(raw_text) if "html" in content_type.lower() or "<html" in raw_text[:500].lower() else raw_text
        text = _collapse_blank_lines(text).strip()
        truncated = len(text) > limit
        if truncated:
            text = text[:limit] + "\n[content truncated]"
        return ToolResult(
            content=text,
            metadata={
                "url": str(response.url),
                "status_code": response.status_code,
                "content_type": content_type,
                "truncated": truncated,
            },
        )


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in {"p", "br", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped + " ")


def _html_to_text(content: str) -> str:
    parser = _TextExtractor()
    parser.feed(content)
    return "".join(parser.parts)


def _collapse_blank_lines(content: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in content.splitlines()]
    collapsed = "\n".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", collapsed)
