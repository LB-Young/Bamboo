"""Shared helpers for the built-in douyin-reach skill."""

from __future__ import annotations

import html
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from bamboo.helpers.config import load_builtin_skill_variables

FALLBACK_USER_AGENT = "Mozilla/5.0 Bamboo Douyin Reach/1"
FALLBACK_REFERER = "https://www.douyin.com/"
DEFAULT_DOWNLOAD_DIR = "douyin-downloads"
DEFAULT_MAX_DOWNLOAD_MB = 200
DOUYIN_HOSTS = {"douyin.com", "www.douyin.com", "v.douyin.com", "iesdouyin.com", "www.iesdouyin.com"}
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
VIDEO_ID_RE = re.compile(r"(?:/video/|modal_id=|aweme_id=|vid=)(\d{8,30})")
USER_ID_RE = re.compile(r"/user/([0-9A-Za-z_\-]+)")
COLLECTION_ID_RE = re.compile(r"(?:/collection/|/series/|collection_id=|mix_id=)([0-9A-Za-z_\-]{6,40})")
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


def skill_variables() -> dict[str, Any]:
    return load_builtin_skill_variables("douyin-reach")


def request_headers() -> dict[str, str]:
    variables = skill_variables()
    user_agent = os.environ.get("DOUYIN_REACH_USER_AGENT") or str(
        variables.get("DOUYIN_REACH_USER_AGENT") or FALLBACK_USER_AGENT
    )
    referer = os.environ.get("DOUYIN_REACH_REFERER") or str(variables.get("DOUYIN_REACH_REFERER") or FALLBACK_REFERER)
    return {
        "User-Agent": user_agent,
        "Referer": referer,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def download_dir() -> Path:
    variables = skill_variables()
    raw = os.environ.get("DOUYIN_REACH_DOWNLOAD_DIR") or str(
        variables.get("DOUYIN_REACH_DOWNLOAD_DIR") or DEFAULT_DOWNLOAD_DIR
    )
    return Path(raw).expanduser()


def max_download_bytes() -> int:
    variables = skill_variables()
    raw = os.environ.get("DOUYIN_REACH_MAX_DOWNLOAD_MB") or str(
        variables.get("DOUYIN_REACH_MAX_DOWNLOAD_MB") or DEFAULT_MAX_DOWNLOAD_MB
    )
    try:
        megabytes = max(1, int(raw))
    except ValueError:
        megabytes = DEFAULT_MAX_DOWNLOAD_MB
    return megabytes * 1024 * 1024


def fetch_html(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers=request_headers())
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


def resolve_public_url(url: str) -> str:
    request = urllib.request.Request(url, headers=request_headers(), method="GET")
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    try:
        with opener.open(request, timeout=30) as response:
            return response.geturl()
    except urllib.error.HTTPError as exc:
        if exc.url:
            return exc.url
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise DouyinError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DouyinError(f"network failure: {exc}") from exc


def is_douyin_url(value: str) -> bool:
    hostname = (urllib.parse.urlparse(value).hostname or "").lower()
    return hostname in DOUYIN_HOSTS or hostname.endswith(".douyin.com") or hostname.endswith(".iesdouyin.com")


def clean_url(value: str) -> str:
    return value.strip().rstrip("，。,.!?！？)")


def extract_urls(text: str) -> list[str]:
    return [clean_url(url) for url in URL_RE.findall(text)]


def extract_video_id(value: str) -> str:
    match = VIDEO_ID_RE.search(value)
    return match.group(1) if match else ""


def extract_user_id(value: str) -> str:
    match = USER_ID_RE.search(value)
    return match.group(1) if match else ""


def extract_collection_id(value: str) -> str:
    match = COLLECTION_ID_RE.search(value)
    return match.group(1) if match else ""


def canonical_video_url(video_id: str) -> str:
    return f"https://www.douyin.com/video/{video_id}" if video_id else ""


def canonical_user_url(user_id: str) -> str:
    return f"https://www.douyin.com/user/{user_id}" if user_id else ""


def looks_like_risk_control(raw_html: str) -> bool:
    lowered = raw_html.lower()
    return any(marker.lower() in lowered for marker in RISK_CONTROL_MARKERS)


def parse_metadata(raw_html: str) -> MetadataParser:
    parser = MetadataParser()
    parser.feed(raw_html)
    return parser
