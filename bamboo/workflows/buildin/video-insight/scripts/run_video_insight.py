#!/usr/bin/env python3
"""Workflow entrypoint for local video insight extraction."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    tokens = shlex.split(argv[0]) if len(argv) == 1 else argv
    parser = argparse.ArgumentParser(description="Run the video-insight workflow.")
    parser.add_argument("video")
    parser.add_argument("positional_output_dir", nargs="?")
    parser.add_argument("--output-dir", dest="output_dir_option")
    args, passthrough = parser.parse_known_args(tokens)

    video_path = Path(args.video).expanduser().resolve()
    if not video_path.is_file():
        print(f"VideoInsightError: video file not found: {video_path}", file=sys.stderr)
        return 1

    selected_output = args.output_dir_option or args.positional_output_dir
    output_dir = Path(selected_output).expanduser() if selected_output else video_path.with_suffix("").parent / f"{video_path.stem}-video-insight"
    output_dir = output_dir.resolve()

    script_dir = Path(__file__).resolve().parent
    command = [
        sys.executable,
        str(script_dir / "process_video.py"),
        str(video_path),
        "--output-dir",
        str(output_dir),
        *passthrough,
    ]
    process = subprocess.run(command, check=False, text=True)
    if process.returncode != 0:
        return process.returncode

    print(f"OutputDir: {output_dir}")
    print_existing("Report", output_dir / "report.json")
    print_existing("Audio", output_dir / "audio.wav")
    print_existing("Keyframes", output_dir / "keyframes")
    print_existing("KeyframesJson", output_dir / "keyframes.json")
    print_existing("KeyframeAnalysis", output_dir / "keyframe_analysis.json")
    print_existing("TranscriptJson", output_dir / "transcript.json")
    print_existing("TranscriptSrt", output_dir / "transcript.srt")
    print_existing("TranscriptVtt", output_dir / "transcript.vtt")
    return 0


def print_existing(label: str, path: Path) -> None:
    if path.exists():
        print(f"{label}: {path}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
