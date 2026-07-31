#!/usr/bin/env python3
"""Minimal public Xiaohongshu helper for Bamboo's xiaohongshu-reach skill."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

from bamboo.helpers.config import load_builtin_skill_variables

FALLBACK_USER_AGENT = "Mozilla/5.0 Bamboo Xiaohongshu Reach/1"
FALLBACK_REFERER = "https://www.xiaohongshu.com/"
XHS_HOSTS = {"www.xiaohongshu.com", "xiaohongshu.com", "xhslink.com"}
NOTE_ID_RE = re.compile(r"(?:/explore/|/discovery/item/|/items/)([0-9a-fA-F]{24}|[0-9A-Za-z]{20,32})")
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
RISK_CONTROL_MARKERS = (
    "verify",
    "captcha",
    "login",
    "安全验证",
    "请登录",
    "访问过于频繁",
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except XiaohongshuError as exc:
        print(f"Xiaohongshu reach error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


class XiaohongshuError(RuntimeError):
    """Raised when a public Xiaohongshu operation cannot be completed."""


class MetadataParser(HTMLParser):
    """Extract basic public metadata from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.in_title = False
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            key = attr_map.get("property") or attr_map.get("name")
            content = attr_map.get("content")
            if key and content:
                self.meta[key] = html.unescape(content).strip()
        if tag.lower() == "link":
            rel = attr_map.get("rel")
            href = attr_map.get("href")
            if rel and href:
                self.links[rel] = href

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return html.unescape("".join(self.title_parts)).strip()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse and inspect public Xiaohongshu note links.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse = subparsers.add_parser("parse", help="Extract Xiaohongshu URLs and note ids from shared text.")
    parse.add_argument("text")
    parse.set_defaults(handler=_cmd_parse)

    note = subparsers.add_parser("note", help="Fetch public metadata for a Xiaohongshu note URL.")
    note.add_argument("url")
    note.set_defaults(handler=_cmd_note)

    search_url = subparsers.add_parser("search-url", help="Build a Xiaohongshu public search URL for a keyword.")
    search_url.add_argument("query")
    search_url.set_defaults(handler=_cmd_search_url)
    return parser


def _cmd_parse(args: argparse.Namespace) -> dict[str, Any]:
    urls = [_clean_url(url) for url in URL_RE.findall(args.text)]
    xhs_urls = [url for url in urls if _is_xiaohongshu_url(url)]
    note_ids = sorted({note_id for url in xhs_urls if (note_id := _extract_note_id(url))})
    return {
        "urls": xhs_urls,
        "note_ids": note_ids,
        "canonical_urls": [_canonical_note_url(note_id) for note_id in note_ids],
    }


def _cmd_note(args: argparse.Namespace) -> dict[str, Any]:
    url = _clean_url(args.url)
    if not _is_xiaohongshu_url(url):
        raise XiaohongshuError("expected a Xiaohongshu or xhslink URL")
    final_url, raw_html = _fetch_html(url)
    parser = MetadataParser()
    parser.feed(raw_html)
    note_id = _extract_note_id(final_url) or _extract_note_id(url) or _extract_note_id(raw_html)
    risk_control = _looks_like_risk_control(raw_html)
    return {
        "input_url": url,
        "final_url": final_url,
        "note_id": note_id,
        "canonical_url": _canonical_note_url(note_id) if note_id else parser.links.get("canonical", ""),
        "title": parser.meta.get("og:title") or parser.title,
        "description": parser.meta.get("description") or parser.meta.get("og:description") or "",
        "og": {
            "title": parser.meta.get("og:title", ""),
            "description": parser.meta.get("og:description", ""),
            "image": parser.meta.get("og:image", ""),
            "url": parser.meta.get("og:url", ""),
        },
        "risk_control_detected": risk_control,
        "public_html_bytes": len(raw_html.encode("utf-8")),
    }


def _cmd_search_url(args: argparse.Namespace) -> dict[str, Any]:
    encoded = urllib.parse.quote(args.query)
    return {
        "query": args.query,
        "url": f"https://www.xiaohongshu.com/search_result?keyword={encoded}",
    }


def _fetch_html(url: str) -> tuple[str, str]:
    variables = load_builtin_skill_variables("xiaohongshu-reach")
    user_agent = os.environ.get("XIAOHONGSHU_REACH_USER_AGENT") or str(
        variables.get("XIAOHONGSHU_REACH_USER_AGENT") or FALLBACK_USER_AGENT
    )
    referer = os.environ.get("XIAOHONGSHU_REACH_REFERER") or str(
        variables.get("XIAOHONGSHU_REACH_REFERER") or FALLBACK_REFERER
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Referer": referer,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read()
            final_url = response.geturl()
            charset = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise XiaohongshuError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise XiaohongshuError(f"network failure: {exc}") from exc
    return final_url, raw.decode(charset, errors="replace")


def _is_xiaohongshu_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").lower()
    return hostname in XHS_HOSTS or hostname.endswith(".xiaohongshu.com")


def _clean_url(value: str) -> str:
    return value.strip().rstrip("，。,.!?！？)")


def _extract_note_id(value: str) -> str:
    match = NOTE_ID_RE.search(value)
    return match.group(1) if match else ""


def _canonical_note_url(note_id: str) -> str:
    return f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""


def _looks_like_risk_control(raw_html: str) -> bool:
    lowered = raw_html.lower()
    return any(marker.lower() in lowered for marker in RISK_CONTROL_MARKERS)


if __name__ == "__main__":
    raise SystemExit(main())
