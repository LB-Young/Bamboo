#!/usr/bin/env python3
"""Unified Douyin helper for Bamboo's douyin-reach skill."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from douyin_common import DouyinError
from douyin_creator import collection_list, creator_analyze_plan, creator_profile
from douyin_public import page_metadata, parse_text, resolve_url, search_url
from douyin_publish import guarded_workflow, publish_plan
from douyin_video import download_public_media, explain_file, extract_audio, transcript, video_info


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except (DouyinError, ValueError) as exc:
        print(f"Douyin reach error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse, inspect, analyze, and plan guarded Douyin workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse = subparsers.add_parser("parse", help="Extract Douyin URLs, video ids, user ids, and collection ids.")
    parse.add_argument("text")
    parse.set_defaults(handler=lambda args: parse_text(args.text))

    resolve = subparsers.add_parser("resolve", help="Resolve a public Douyin short or full URL.")
    resolve.add_argument("url")
    resolve.set_defaults(handler=lambda args: resolve_url(args.url))

    page = subparsers.add_parser("page", help="Fetch public metadata for a Douyin page URL.")
    page.add_argument("url")
    page.set_defaults(handler=lambda args: page_metadata(args.url))

    search = subparsers.add_parser("search-url", help="Build a Douyin public search URL for a keyword.")
    search.add_argument("query")
    search.set_defaults(handler=lambda args: search_url(args.query))

    video = subparsers.add_parser("video-info", help="Fetch public video metadata and media candidates.")
    video.add_argument("url")
    video.set_defaults(handler=lambda args: video_info(args.url))

    download = subparsers.add_parser("download", help="Download a public media URL discovered from a video page.")
    download.add_argument("url")
    download.add_argument("--media-url", default="", help="Use this direct public media URL instead of page extraction.")
    download.add_argument("--output-dir", default="", help="Directory for downloaded media.")
    download.set_defaults(
        handler=lambda args: download_public_media(
            args.url,
            output_dir=args.output_dir or None,
            media_url=args.media_url,
        )
    )

    audio = subparsers.add_parser("extract-audio", help="Extract audio from a local video file using ffmpeg.")
    audio.add_argument("video_path")
    audio.add_argument("--output-path", default="")
    audio.set_defaults(handler=lambda args: extract_audio(args.video_path, output_path=args.output_path))

    transcript_parser = subparsers.add_parser("transcript", help="Read a local transcript sidecar file when available.")
    transcript_parser.add_argument("path")
    transcript_parser.set_defaults(handler=lambda args: transcript(args.path))

    explain = subparsers.add_parser("explain-file", help="Inspect a local video/transcript file and return analysis guidance.")
    explain.add_argument("path")
    explain.set_defaults(handler=lambda args: explain_file(args.path))

    creator = subparsers.add_parser("creator-profile", help="Fetch public metadata for a Douyin creator page.")
    creator.add_argument("url")
    creator.set_defaults(handler=lambda args: creator_profile(args.url))

    collection = subparsers.add_parser("collection-list", help="Fetch public metadata and visible links for a collection page.")
    collection.add_argument("url")
    collection.add_argument("--max-results", type=int, default=30)
    collection.set_defaults(handler=lambda args: collection_list(args.url, max_results=args.max_results))

    creator_analyze = subparsers.add_parser("creator-analyze", help="Build a public creator analysis plan from visible data.")
    creator_analyze.add_argument("url")
    creator_analyze.add_argument("--sample-size", type=int, default=12)
    creator_analyze.set_defaults(handler=lambda args: creator_analyze_plan(args.url, sample_size=args.sample_size))

    publish = subparsers.add_parser("publish-plan", help="Create a guarded Douyin publishing checklist.")
    publish.add_argument("--title", required=True)
    publish.add_argument("--body", default="")
    publish.add_argument("--media", action="append", default=[])
    publish.add_argument("--tag", action="append", default=[])
    publish.add_argument("--account", default="")
    publish.set_defaults(
        handler=lambda args: publish_plan(
            title=args.title,
            body=args.body,
            media=args.media,
            tags=args.tag,
            account=args.account,
        )
    )

    capability = subparsers.add_parser("capability", help="Return supported and guarded Douyin operations.")
    capability.set_defaults(handler=lambda _args: _capability())
    return parser


def _capability() -> dict[str, Any]:
    return {
        "modules": {
            "public": ["parse", "resolve", "page", "search-url"],
            "video": ["video-info", "download", "extract-audio", "transcript", "explain-file"],
            "creator": ["creator-profile", "collection-list", "creator-analyze"],
            "publish": ["publish-plan"],
        },
        "safety_levels": guarded_workflow(),
        "requires_explicit_user_confirmation": [
            "login",
            "publish",
            "like",
            "favorite",
            "share",
            "account-switch",
        ],
        "unsupported_by_default": [
            "comment",
            "reply-comment",
            "private-message",
            "creator-center-analytics",
            "bulk-operations",
            "captcha-bypass",
            "cookie-reading",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
