#!/usr/bin/env python3
"""Minimal public YouTube helper for Bamboo's youtube-reach skill."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any

from bamboo.helpers.config import load_builtin_skill_variables

FALLBACK_LANGUAGES = "en,zh-Hans,zh-Hant,zh-CN,zh-TW"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except ReachError as exc:
        print(f"YouTube reach error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


class ReachError(RuntimeError):
    """Raised when a YouTube operation cannot be completed."""


def _build_parser() -> argparse.ArgumentParser:
    variables = load_builtin_skill_variables("youtube-reach")
    parser = argparse.ArgumentParser(description="Inspect public YouTube metadata with yt-dlp.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="Fetch public metadata for a video or URL.")
    info.add_argument("url")
    info.set_defaults(handler=_cmd_info)

    transcript = subparsers.add_parser("transcript", help="Fetch available public captions metadata and subtitle URLs.")
    transcript.add_argument("url")
    transcript.add_argument(
        "--languages",
        default=os.environ.get("YOUTUBE_REACH_LANGUAGES")
        or str(variables.get("YOUTUBE_REACH_LANGUAGES") or FALLBACK_LANGUAGES),
        help="Comma-separated language preference list.",
    )
    transcript.set_defaults(handler=_cmd_transcript)

    playlist = subparsers.add_parser("playlist", help="Fetch playlist or channel entries.")
    playlist.add_argument("url")
    playlist.add_argument("--flat", action="store_true", help="Use flat extraction for faster listing.")
    playlist.add_argument("--max-results", type=int, default=25)
    playlist.set_defaults(handler=_cmd_playlist)
    return parser


def _cmd_info(args: argparse.Namespace) -> dict[str, Any]:
    data = _yt_dlp_json(args.url, extra_args=[])
    return _video_summary(data)


def _cmd_transcript(args: argparse.Namespace) -> dict[str, Any]:
    data = _yt_dlp_json(args.url, extra_args=["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", args.languages])
    subtitles = _subtitle_summary(data.get("subtitles", {}))
    automatic = _subtitle_summary(data.get("automatic_captions", {}))
    return {
        **_video_summary(data),
        "subtitles": subtitles,
        "automatic_captions": automatic,
        "language_preference": [item.strip() for item in args.languages.split(",") if item.strip()],
    }


def _cmd_playlist(args: argparse.Namespace) -> dict[str, Any]:
    extra = ["--flat-playlist"] if args.flat else []
    data = _yt_dlp_json(args.url, extra_args=extra)
    entries = data.get("entries") or []
    if not isinstance(entries, list):
        entries = []
    limit = max(1, min(args.max_results, 100))
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "webpage_url": data.get("webpage_url") or args.url,
        "extractor": data.get("extractor"),
        "entry_count": len(entries),
        "entries": [_entry_summary(entry) for entry in entries[:limit] if isinstance(entry, dict)],
    }


def _yt_dlp_json(url: str, *, extra_args: list[str]) -> dict[str, Any]:
    executable = shutil.which("yt-dlp")
    if executable is None:
        raise ReachError("yt-dlp is not installed or not on PATH")
    command = [executable, "--dump-json", "--no-warnings", *extra_args, url]
    process = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    if process.returncode != 0:
        raise ReachError((process.stderr or process.stdout or "yt-dlp failed").strip()[:1000])
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    if not lines:
        raise ReachError("yt-dlp returned no JSON")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise ReachError(f"yt-dlp returned invalid JSON: {lines[-1][:300]}") from exc


def _video_summary(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "channel": data.get("channel") or data.get("uploader"),
        "channel_id": data.get("channel_id") or data.get("uploader_id"),
        "duration": data.get("duration"),
        "upload_date": data.get("upload_date"),
        "view_count": data.get("view_count"),
        "like_count": data.get("like_count"),
        "webpage_url": data.get("webpage_url"),
        "description": data.get("description"),
        "tags": data.get("tags") or [],
    }


def _entry_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "title": entry.get("title"),
        "url": entry.get("url") or entry.get("webpage_url"),
        "duration": entry.get("duration"),
        "channel": entry.get("channel") or entry.get("uploader"),
    }


def _subtitle_summary(subtitle_map: object) -> dict[str, list[dict[str, str]]]:
    if not isinstance(subtitle_map, dict):
        return {}
    output: dict[str, list[dict[str, str]]] = {}
    for language, entries in subtitle_map.items():
        if not isinstance(entries, list):
            continue
        output[str(language)] = [
            {"ext": str(item.get("ext") or ""), "url": str(item.get("url") or "")}
            for item in entries
            if isinstance(item, dict)
        ]
    return output


if __name__ == "__main__":
    raise SystemExit(main())
