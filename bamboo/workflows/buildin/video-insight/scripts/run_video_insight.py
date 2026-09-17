#!/usr/bin/env python3
"""Workflow entrypoint for local video insight extraction."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    load_env_file()
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

    output_dir = resolve_output_dir(video_path, args.output_dir_option or args.positional_output_dir)

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


def resolve_output_dir(video_path: Path, selected_output: str | None) -> Path:
    if selected_output:
        return Path(selected_output).expanduser().resolve()

    root = os.environ.get("VIDEO_INSIGHT_OUTPUT_DIR")
    if root:
        base_dir = Path(root).expanduser()
    else:
        base_dir = Path.home() / ".bamboo" / "workspace" / "video-insight"
    return unique_child_dir(base_dir.resolve(), video_path.stem)


def unique_child_dir(base_dir: Path, name: str) -> Path:
    safe_name = safe_path_name(name) or "video"
    candidate = base_dir / safe_name
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = base_dir / f"{safe_name}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def safe_path_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value.strip())
    cleaned = cleaned.strip("._")
    return cleaned[:120]


def load_env_file() -> None:
    for path in (Path.home() / ".bamboo" / ".env", Path.home() / ".Bamboo" / ".env"):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            parsed = parse_env_line(raw_line)
            if parsed is None:
                continue
            key, value = parsed
            os.environ.setdefault(key, value)


def parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].lstrip()
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
