#!/usr/bin/env python3
"""Minimal public Douyin helper for Bamboo's douyin-reach skill."""

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

FALLBACK_USER_AGENT = "Mozilla/5.0 Bamboo Douyin Reach/1"
FALLBACK_REFERER = "https://www.douyin.com/"
DOUYIN_HOSTS = {"douyin.com", "www.douyin.com", "v.douyin.com", "iesdouyin.com", "www.iesdouyin.com"}
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
VIDEO_ID_RE = re.compile(r"(?:/video/|modal_id=|aweme_id=|vid=)(\d{8,30})")
USER_ID_RE = re.compile(r"/user/([0-9A-Za-z_\-]+)")
RISK_CONTROL_MARKERS = (
    "captcha",
    "verify",
    "login",
    "验证码",
    "安全验证",
    "请登录",
    "访问过于频繁",
    "系统繁忙",
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except DouyinError as exc:
        print(f"Douyin reach error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


class DouyinError(RuntimeError):
    """Raised when a public Douyin operation cannot be completed."""


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
    parser = argparse.ArgumentParser(description="Parse and inspect public Douyin links.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse = subparsers.add_parser("parse", help="Extract Douyin URLs, video ids, and user ids from shared text.")
    parse.add_argument("text")
    parse.set_defaults(handler=_cmd_parse)

    page = subparsers.add_parser("page", help="Fetch public metadata for a Douyin page URL.")
    page.add_argument("url")
    page.set_defaults(handler=_cmd_page)

    search_url = subparsers.add_parser("search-url", help="Build a Douyin public search URL for a keyword.")
    search_url.add_argument("query")
    search_url.set_defaults(handler=_cmd_search_url)

    capability = subparsers.add_parser("capability", help="Return supported and guarded Douyin operations.")
    capability.set_defaults(handler=_cmd_capability)
    return parser


def _cmd_parse(args: argparse.Namespace) -> dict[str, Any]:
    urls = [_clean_url(url) for url in URL_RE.findall(args.text)]
    douyin_urls = [url for url in urls if _is_douyin_url(url)]
    video_ids = sorted({video_id for value in [*douyin_urls, args.text] if (video_id := _extract_video_id(value))})
    user_ids = sorted({user_id for value in douyin_urls if (user_id := _extract_user_id(value))})
    return {
        "urls": douyin_urls,
        "video_ids": video_ids,
        "user_ids": user_ids,
        "canonical_video_urls": [_canonical_video_url(video_id) for video_id in video_ids],
    }


def _cmd_page(args: argparse.Namespace) -> dict[str, Any]:
    url = _clean_url(args.url)
    if not _is_douyin_url(url):
        raise DouyinError("expected a Douyin URL")
    final_url, raw_html = _fetch_html(url)
    parser = MetadataParser()
    parser.feed(raw_html)
    video_id = _extract_video_id(final_url) or _extract_video_id(url) or _extract_video_id(raw_html)
    user_id = _extract_user_id(final_url) or _extract_user_id(url)
    return {
        "input_url": url,
        "final_url": final_url,
        "video_id": video_id,
        "user_id": user_id,
        "canonical_url": _canonical_video_url(video_id) if video_id else parser.links.get("canonical", ""),
        "title": parser.meta.get("og:title") or parser.title,
        "description": parser.meta.get("description") or parser.meta.get("og:description") or "",
        "og": {
            "title": parser.meta.get("og:title", ""),
            "description": parser.meta.get("og:description", ""),
            "image": parser.meta.get("og:image", ""),
            "url": parser.meta.get("og:url", ""),
            "video": parser.meta.get("og:video") or parser.meta.get("og:video:url") or "",
        },
        "risk_control_detected": _looks_like_risk_control(raw_html),
        "public_html_bytes": len(raw_html.encode("utf-8")),
    }


def _cmd_search_url(args: argparse.Namespace) -> dict[str, Any]:
    encoded = urllib.parse.quote(args.query)
    return {"query": args.query, "url": f"https://www.douyin.com/search/{encoded}"}


def _cmd_capability(_: argparse.Namespace) -> dict[str, Any]:
    return {
        "safe_helper_commands": {
            "parse": "Extract public Douyin URLs, video ids, user ids, and canonical links from text.",
            "page": "Fetch public HTML metadata for a Douyin page URL.",
            "search-url": "Build a Douyin search URL for manual/public browsing.",
        },
        "guarded_browser_workflows": {
            "auth": ["check-login", "qr-login", "sms-code-login", "account-switch"],
            "explore": ["search-videos", "get-video-detail"],
            "publish": ["image-post-publish", "music-selection", "final-publish-click"],
            "interact": ["like-video", "favorite-video", "share-video"],
        },
        "unsupported_by_default": [
            "comment",
            "reply-comment",
            "private-message",
            "creator-center-analytics",
            "bulk-operations",
            "captcha-bypass",
            "cookie-reading",
        ],
        "requires_explicit_user_confirmation": [
            "login",
            "publish",
            "like",
            "favorite",
            "share",
            "account-switch",
        ],
    }


def _fetch_html(url: str) -> tuple[str, str]:
    variables = load_builtin_skill_variables("douyin-reach")
    user_agent = os.environ.get("DOUYIN_REACH_USER_AGENT") or str(
        variables.get("DOUYIN_REACH_USER_AGENT") or FALLBACK_USER_AGENT
    )
    referer = os.environ.get("DOUYIN_REACH_REFERER") or str(variables.get("DOUYIN_REACH_REFERER") or FALLBACK_REFERER)
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
        raise DouyinError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DouyinError(f"network failure: {exc}") from exc
    return final_url, raw.decode(charset, errors="replace")


def _is_douyin_url(value: str) -> bool:
    hostname = (urllib.parse.urlparse(value).hostname or "").lower()
    return hostname in DOUYIN_HOSTS or hostname.endswith(".douyin.com") or hostname.endswith(".iesdouyin.com")


def _clean_url(value: str) -> str:
    return value.strip().rstrip("，。,.!?！？)")


def _extract_video_id(value: str) -> str:
    match = VIDEO_ID_RE.search(value)
    return match.group(1) if match else ""


def _extract_user_id(value: str) -> str:
    match = USER_ID_RE.search(value)
    return match.group(1) if match else ""


def _canonical_video_url(video_id: str) -> str:
    return f"https://www.douyin.com/video/{video_id}" if video_id else ""


def _looks_like_risk_control(raw_html: str) -> bool:
    lowered = raw_html.lower()
    return any(marker.lower() in lowered for marker in RISK_CONTROL_MARKERS)


if __name__ == "__main__":
    raise SystemExit(main())
