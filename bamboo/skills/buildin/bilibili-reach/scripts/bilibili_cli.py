#!/usr/bin/env python3
"""Minimal public Bilibili helper for Bamboo's bilibili-reach skill."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from bamboo.helpers.config import load_builtin_skill_variables

SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
VIEW_API = "https://api.bilibili.com/x/web-interface/view"
BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
FALLBACK_USER_AGENT = "Mozilla/5.0 Bamboo Bilibili Reach/1"
FALLBACK_REFERER = "https://www.bilibili.com/"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except BilibiliError as exc:
        print(f"Bilibili reach error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


class BilibiliError(RuntimeError):
    """Raised when a public Bilibili request cannot be completed."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search and inspect public Bilibili videos.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search public Bilibili videos by keyword.")
    search.add_argument("query")
    search.add_argument("--max-results", type=int, default=10)
    search.set_defaults(handler=_cmd_search)

    video = subparsers.add_parser("video", help="Fetch public metadata for a BV id or Bilibili video URL.")
    video.add_argument("bvid_or_url")
    video.set_defaults(handler=_cmd_video)
    return parser


def _cmd_search(args: argparse.Namespace) -> dict[str, Any]:
    params = {
        "search_type": "video",
        "keyword": args.query,
        "page": "1",
    }
    data = _get_json(SEARCH_API, params)
    results = data.get("data", {}).get("result", [])
    if not isinstance(results, list):
        results = []
    limit = max(1, min(args.max_results, 50))
    return {
        "query": args.query,
        "results": [_search_result(item) for item in results[:limit] if isinstance(item, dict)],
    }


def _cmd_video(args: argparse.Namespace) -> dict[str, Any]:
    bvid = _extract_bvid(args.bvid_or_url)
    if not bvid:
        raise BilibiliError("expected a BV id or Bilibili video URL")
    data = _get_json(VIEW_API, {"bvid": bvid})
    video = data.get("data")
    if not isinstance(video, dict):
        raise BilibiliError("Bilibili response did not contain video data")
    return _video_result(video)


def _get_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    variables = load_builtin_skill_variables("bilibili-reach")
    user_agent = os.environ.get("BILIBILI_REACH_USER_AGENT") or str(
        variables.get("BILIBILI_REACH_USER_AGENT") or FALLBACK_USER_AGENT
    )
    referer = os.environ.get("BILIBILI_REACH_REFERER") or str(
        variables.get("BILIBILI_REACH_REFERER") or FALLBACK_REFERER
    )
    request = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": user_agent,
            "Referer": referer,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise BilibiliError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise BilibiliError(f"network failure: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BilibiliError(f"invalid JSON response: {raw[:300]}") from exc
    if data.get("code") not in (0, "0"):
        raise BilibiliError(f"Bilibili API code={data.get('code')} message={data.get('message')}")
    return data


def _search_result(item: dict[str, Any]) -> dict[str, Any]:
    bvid = str(item.get("bvid") or "")
    return {
        "bvid": bvid,
        "title": _strip_html(str(item.get("title") or "")),
        "url": f"https://www.bilibili.com/video/{bvid}" if bvid else str(item.get("arcurl") or ""),
        "author": item.get("author"),
        "mid": item.get("mid"),
        "duration": item.get("duration"),
        "play": item.get("play"),
        "favorites": item.get("favorites"),
        "pubdate": _format_timestamp(item.get("pubdate")),
        "description": item.get("description"),
    }


def _video_result(video: dict[str, Any]) -> dict[str, Any]:
    owner = video.get("owner") if isinstance(video.get("owner"), dict) else {}
    stat = video.get("stat") if isinstance(video.get("stat"), dict) else {}
    pages = video.get("pages") if isinstance(video.get("pages"), list) else []
    bvid = str(video.get("bvid") or "")
    return {
        "bvid": bvid,
        "aid": video.get("aid"),
        "title": video.get("title"),
        "url": f"https://www.bilibili.com/video/{bvid}" if bvid else "",
        "owner": {"mid": owner.get("mid"), "name": owner.get("name")},
        "duration": video.get("duration"),
        "pubdate": _format_timestamp(video.get("pubdate")),
        "description": video.get("desc"),
        "stats": {
            "view": stat.get("view"),
            "danmaku": stat.get("danmaku"),
            "reply": stat.get("reply"),
            "favorite": stat.get("favorite"),
            "coin": stat.get("coin"),
            "share": stat.get("share"),
            "like": stat.get("like"),
        },
        "pages": [
            {"cid": page.get("cid"), "page": page.get("page"), "part": page.get("part"), "duration": page.get("duration")}
            for page in pages
            if isinstance(page, dict)
        ],
    }


def _extract_bvid(value: str) -> str:
    match = BV_RE.search(value)
    return match.group(1) if match else ""


def _format_timestamp(value: object) -> str:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


if __name__ == "__main__":
    raise SystemExit(main())
