#!/usr/bin/env python3
"""Minimal RSS/Atom reader for Bamboo's rss-reach skill."""

from __future__ import annotations

import argparse
import email.utils
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from bamboo.helpers.config import load_builtin_skill_variables


ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
FALLBACK_USER_AGENT = "Bamboo RSS Reach/1"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except RssError as exc:
        print(f"RSS reach error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


class RssError(RuntimeError):
    """Raised when a feed cannot be read or parsed."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read public RSS or Atom feeds.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    read = subparsers.add_parser("read", help="Read recent feed entries.")
    read.add_argument("url")
    read.add_argument("--max-items", type=int, default=20)
    read.set_defaults(handler=_cmd_read)

    latest = subparsers.add_parser("latest", help="Read the newest feed entry.")
    latest.add_argument("url")
    latest.set_defaults(handler=_cmd_latest)

    check = subparsers.add_parser("check", help="Return entries newer than --since.")
    check.add_argument("url")
    check.add_argument("--since", required=True, help="ISO timestamp or RFC 2822 timestamp.")
    check.set_defaults(handler=_cmd_check)
    return parser


def _cmd_read(args: argparse.Namespace) -> dict[str, Any]:
    feed = _fetch_feed(args.url)
    limit = max(1, min(args.max_items, 100))
    feed["entries"] = feed["entries"][:limit]
    return feed


def _cmd_latest(args: argparse.Namespace) -> dict[str, Any]:
    feed = _fetch_feed(args.url)
    entries = feed["entries"]
    return {**{key: value for key, value in feed.items() if key != "entries"}, "latest": entries[0] if entries else None}


def _cmd_check(args: argparse.Namespace) -> dict[str, Any]:
    threshold = _parse_date(args.since)
    feed = _fetch_feed(args.url)
    changed = []
    for entry in feed["entries"]:
        stamp = _parse_date(str(entry.get("published") or entry.get("updated") or ""))
        if stamp and threshold and stamp > threshold:
            changed.append(entry)
    return {
        **{key: value for key, value in feed.items() if key != "entries"},
        "since": args.since,
        "changed": bool(changed),
        "entries": changed,
    }


def _fetch_feed(url: str) -> dict[str, Any]:
    variables = load_builtin_skill_variables("rss-reach")
    user_agent = os.environ.get("RSS_REACH_USER_AGENT") or str(
        variables.get("RSS_REACH_USER_AGENT") or FALLBACK_USER_AGENT
    )
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.URLError as exc:
        raise RssError(f"network failure: {exc}") from exc
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RssError(f"invalid XML feed: {exc}") from exc
    if root.tag == f"{ATOM}feed":
        return _parse_atom(root, url)
    return _parse_rss(root, url)


def _parse_atom(root: ET.Element, url: str) -> dict[str, Any]:
    entries = [_atom_entry(entry) for entry in root.findall(f"{ATOM}entry")]
    return {
        "url": url,
        "format": "atom",
        "title": _text(root.find(f"{ATOM}title")),
        "link": _atom_link(root),
        "updated": _text(root.find(f"{ATOM}updated")),
        "entries": _sort_entries(entries),
    }


def _parse_rss(root: ET.Element, url: str) -> dict[str, Any]:
    channel = root.find("channel") or root
    entries = [_rss_entry(item) for item in channel.findall("item")]
    return {
        "url": url,
        "format": "rss",
        "title": _text(channel.find("title")),
        "link": _text(channel.find("link")),
        "updated": _text(channel.find("lastBuildDate")) or _text(channel.find("pubDate")),
        "entries": _sort_entries(entries),
    }


def _rss_entry(item: ET.Element) -> dict[str, Any]:
    return {
        "id": _text(item.find("guid")) or _text(item.find("link")),
        "title": _text(item.find("title")),
        "link": _text(item.find("link")),
        "published": _text(item.find("pubDate")),
        "updated": _text(item.find("updated")),
        "summary": _text(item.find("description")) or _text(item.find(f"{CONTENT}encoded")),
    }


def _atom_entry(entry: ET.Element) -> dict[str, Any]:
    return {
        "id": _text(entry.find(f"{ATOM}id")) or _atom_link(entry),
        "title": _text(entry.find(f"{ATOM}title")),
        "link": _atom_link(entry),
        "published": _text(entry.find(f"{ATOM}published")),
        "updated": _text(entry.find(f"{ATOM}updated")),
        "summary": _text(entry.find(f"{ATOM}summary")) or _text(entry.find(f"{ATOM}content")),
    }


def _sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda item: _parse_date(str(item.get("published") or item.get("updated") or "")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def _atom_link(root: ET.Element) -> str:
    for link in root.findall(f"{ATOM}link"):
        if link.attrib.get("rel", "alternate") == "alternate" and link.attrib.get("href"):
            return link.attrib["href"]
    link = root.find(f"{ATOM}link")
    return link.attrib.get("href", "") if link is not None else ""


def _text(element: ET.Element | None) -> str:
    return "".join(element.itertext()).strip() if element is not None else ""


def _parse_date(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
