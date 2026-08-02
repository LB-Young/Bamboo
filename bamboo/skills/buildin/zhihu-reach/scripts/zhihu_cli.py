#!/usr/bin/env python3
"""Minimal public Zhihu helper for Bamboo's zhihu-reach skill."""

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

FALLBACK_USER_AGENT = "Mozilla/5.0 Bamboo Zhihu Reach/1"
FALLBACK_REFERER = "https://www.zhihu.com/"
ZH_HOSTS = {"zhihu.com", "www.zhihu.com", "zhuanlan.zhihu.com", "link.zhihu.com"}
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
QUESTION_RE = re.compile(r"/question/(\d+)")
ANSWER_RE = re.compile(r"/answer/(\d+)")
ARTICLE_RE = re.compile(r"zhuanlan\.zhihu\.com/p/(\d+)|/p/(\d+)")
ZVIDEO_RE = re.compile(r"/zvideo/(\d+)")
RISK_CONTROL_MARKERS = ("captcha", "login", "安全验证", "请登录", "登录后", "访问过于频繁")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except ZhihuError as exc:
        print(f"Zhihu reach error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


class ZhihuError(RuntimeError):
    """Raised when a public Zhihu operation cannot be completed."""


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
    parser = argparse.ArgumentParser(description="Parse and inspect public Zhihu links.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse = subparsers.add_parser("parse", help="Extract Zhihu URLs and entities from shared text.")
    parse.add_argument("text")
    parse.set_defaults(handler=_cmd_parse)

    page = subparsers.add_parser("page", help="Fetch public metadata for a Zhihu page URL.")
    page.add_argument("url")
    page.set_defaults(handler=_cmd_page)

    search_url = subparsers.add_parser("search-url", help="Build a Zhihu public search URL for a keyword.")
    search_url.add_argument("query")
    search_url.set_defaults(handler=_cmd_search_url)
    return parser


def _cmd_parse(args: argparse.Namespace) -> dict[str, Any]:
    urls = [_clean_url(url) for url in URL_RE.findall(args.text)]
    zhihu_urls = [url for url in urls if _is_zhihu_url(url)]
    return {"urls": zhihu_urls, "entities": [_entity_from_url(url) for url in zhihu_urls]}


def _cmd_page(args: argparse.Namespace) -> dict[str, Any]:
    url = _clean_url(args.url)
    if not _is_zhihu_url(url):
        raise ZhihuError("expected a Zhihu URL")
    final_url, raw_html = _fetch_html(url)
    parser = MetadataParser()
    parser.feed(raw_html)
    return {
        "input_url": url,
        "final_url": final_url,
        "entity": _entity_from_url(final_url) or _entity_from_url(url),
        "canonical_url": parser.links.get("canonical", ""),
        "title": parser.meta.get("og:title") or parser.title,
        "description": parser.meta.get("description") or parser.meta.get("og:description") or "",
        "og": {
            "title": parser.meta.get("og:title", ""),
            "description": parser.meta.get("og:description", ""),
            "image": parser.meta.get("og:image", ""),
            "url": parser.meta.get("og:url", ""),
        },
        "risk_control_detected": _looks_like_risk_control(raw_html),
        "public_html_bytes": len(raw_html.encode("utf-8")),
    }


def _cmd_search_url(args: argparse.Namespace) -> dict[str, Any]:
    encoded = urllib.parse.quote(args.query)
    return {"query": args.query, "url": f"https://www.zhihu.com/search?type=content&q={encoded}"}


def _fetch_html(url: str) -> tuple[str, str]:
    variables = load_builtin_skill_variables("zhihu-reach")
    user_agent = os.environ.get("ZHIHU_REACH_USER_AGENT") or str(
        variables.get("ZHIHU_REACH_USER_AGENT") or FALLBACK_USER_AGENT
    )
    referer = os.environ.get("ZHIHU_REACH_REFERER") or str(variables.get("ZHIHU_REACH_REFERER") or FALLBACK_REFERER)
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
        raise ZhihuError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ZhihuError(f"network failure: {exc}") from exc
    return final_url, raw.decode(charset, errors="replace")


def _is_zhihu_url(value: str) -> bool:
    hostname = (urllib.parse.urlparse(value).hostname or "").lower()
    return hostname in ZH_HOSTS or hostname.endswith(".zhihu.com")


def _entity_from_url(url: str) -> dict[str, str]:
    question = QUESTION_RE.search(url)
    answer = ANSWER_RE.search(url)
    article = ARTICLE_RE.search(url)
    zvideo = ZVIDEO_RE.search(url)
    if answer:
        return {"type": "answer", "id": answer.group(1), "question_id": question.group(1) if question else ""}
    if question:
        return {"type": "question", "id": question.group(1)}
    if article:
        return {"type": "article", "id": article.group(1) or article.group(2)}
    if zvideo:
        return {"type": "zvideo", "id": zvideo.group(1)}
    return {"type": "unknown", "id": ""}


def _clean_url(value: str) -> str:
    return value.strip().rstrip("，。,.!?！？)")


def _looks_like_risk_control(raw_html: str) -> bool:
    lowered = raw_html.lower()
    return any(marker.lower() in lowered for marker in RISK_CONTROL_MARKERS)


if __name__ == "__main__":
    raise SystemExit(main())
