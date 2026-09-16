#!/usr/bin/env python3
"""Extract 16 kHz mono WAV audio from a local video file with ffmpeg."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract 16 kHz mono WAV audio from a local video file.")
    parser.add_argument("video")
    parser.add_argument("--output", required=True)
    parser.add_argument("--sample-rate", type=int, default=16000)
    args = parser.parse_args(argv)

    try:
        result = extract_audio(Path(args.video), Path(args.output), args.sample_rate)
    except RuntimeError as exc:
        print(f"Video insight error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def extract_audio(video: Path, output: Path, sample_rate: int) -> dict[str, Any]:
    if not video.is_file():
        raise RuntimeError(f"video file not found: {video}")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        str(output),
    ]
    process = subprocess.run(command, check=False, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError((process.stderr or process.stdout or "ffmpeg failed").strip()[-2000:])
    return {
        "video": str(video),
        "audio": str(output),
        "sample_rate": sample_rate,
        "bytes": output.stat().st_size,
    }


if __name__ == "__main__":
    raise SystemExit(main())
