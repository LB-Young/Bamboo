#!/usr/bin/env python3
"""Download a Bilibili video directly with yt-dlp, without RedFox or an API key.

Dependency: python -m pip install -U 'yt-dlp>=2026.8.19'
Install ffmpeg to merge separate video and audio streams at higher quality.
Documentation: https://github.com/yt-dlp/yt-dlp#usage-and-options

Input example:
    python download_video_free.py https://www.bilibili.com/video/BV1AmSSBMEqo/ --output-dir ./downloads
Output: JSON-quoted final file paths on stdout; progress/errors on stderr.
Exit status: 0 means downloaded; nonzero means the caller may try download_video.py.
This script never calls the paid API itself.
"""

from __future__ import annotations

import argparse
import importlib.util
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download Bilibili videos for free")
    parser.add_argument("url")
    parser.add_argument("--output-dir", default="./downloads")
    parser.add_argument("--cookies", help="Optional Netscape cookies file")
    parser.add_argument("--timeout", type=int, default=600, help="Total timeout in seconds")
    args = parser.parse_args(argv)
    parsed = urlparse(args.url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not (
        host == "bilibili.com" or host.endswith(".bilibili.com") or host == "b23.tv"
    ):
        parser.error("Expected a Bilibili or b23.tv video URL")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if importlib.util.find_spec("yt_dlp") is None:
        print("Missing yt-dlp: install with python -m pip install -U yt-dlp", file=sys.stderr)
        return 1
    # Old Bilibili extractors can fail with HTTP 412 even for public videos.
    installed = version("yt-dlp")
    release = tuple(int(part) for part in installed.split(".")[:3])
    if release < (2026, 8, 19):
        print(
            f"yt-dlp {installed} is too old for this downloader. "
            "Update with: python -m pip install -U 'yt-dlp>=2026.8.19'",
            file=sys.stderr,
        )
        return 1
    command = [
        sys.executable, "-m", "yt_dlp",
        "--ignore-config", "--no-playlist", "--no-simulate",
        "--socket-timeout", "30", "--retries", "2", "--fragment-retries", "2",
        "--abort-on-unavailable-fragments",
        "--paths", str(Path(args.output_dir).expanduser().resolve()),
        "--output", "%(id)s.%(ext)s",
        "--print", "after_move:%(filepath)j",
    ]
    if args.cookies:
        command.extend(["--cookies", str(Path(args.cookies).expanduser())])
    command.extend(["--", args.url])
    try:
        return subprocess.run(command, timeout=args.timeout, check=False).returncode
    except subprocess.TimeoutExpired:
        print(f"Free download timed out after {args.timeout}s", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Free download failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
