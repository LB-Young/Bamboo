#!/usr/bin/env python3
"""Extract scene-change keyframes from a local video file with ffmpeg."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PTS_RE = re.compile(r"pts_time:([0-9.]+)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract scene-change keyframes from a local video file.")
    parser.add_argument("video")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scene-threshold", type=float, default=0.35)
    parser.add_argument("--max-width", type=int, default=1280)
    parser.add_argument("--fallback-interval", type=float, default=10.0)
    args = parser.parse_args(argv)

    try:
        result = extract_keyframes(
            Path(args.video),
            Path(args.output_dir),
            scene_threshold=args.scene_threshold,
            max_width=args.max_width,
            fallback_interval=args.fallback_interval,
        )
    except RuntimeError as exc:
        print(f"Video insight error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def extract_keyframes(
    video: Path,
    output_dir: Path,
    *,
    scene_threshold: float,
    max_width: int,
    fallback_interval: float,
) -> dict[str, Any]:
    if not video.is_file():
        raise RuntimeError(f"video file not found: {video}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("frame_*.jpg"):
        old.unlink()

    pattern = output_dir / "frame_%06d.jpg"
    scale = f"scale='min({max_width},iw)':-2,format=yuvj420p"
    vf = f"select='gt(scene,{scene_threshold})',showinfo,{scale}"
    process = subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vf", vf, "-vsync", "vfr", str(pattern)],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0 and not sorted(output_dir.glob("frame_*.jpg")):
        return _extract_fallback_frames(video, output_dir, max_width=max_width, interval=fallback_interval)
    if process.returncode != 0:
        raise RuntimeError((process.stderr or process.stdout or "ffmpeg failed").strip()[-2000:])

    frames = sorted(output_dir.glob("frame_*.jpg"))
    times = [float(match.group(1)) for match in PTS_RE.finditer(process.stderr or "")]
    if len(frames) < 2:
        for frame in frames:
            frame.unlink()
        return _extract_fallback_frames(video, output_dir, max_width=max_width, interval=fallback_interval)

    entries = []
    for index, frame in enumerate(frames):
        entries.append(
            {
                "index": index + 1,
                "time": times[index] if index < len(times) else None,
                "path": str(frame),
                "bytes": frame.stat().st_size,
                "method": "scene",
            }
        )
    output_json = output_dir.parent / "keyframes.json"
    data = {"video": str(video), "scene_threshold": scene_threshold, "frames": entries}
    output_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _extract_fallback_frames(video: Path, output_dir: Path, *, max_width: int, interval: float) -> dict[str, Any]:
    pattern = output_dir / "frame_%06d.jpg"
    scale = f"scale='min({max_width},iw)':-2,format=yuvj420p"
    vf = f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{interval})',showinfo,{scale}"
    process = subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vf", vf, "-vsync", "vfr", str(pattern)],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise RuntimeError((process.stderr or process.stdout or "fallback ffmpeg failed").strip()[-2000:])
    frames = sorted(output_dir.glob("frame_*.jpg"))
    times = [float(match.group(1)) for match in PTS_RE.finditer(process.stderr or "")]
    if not frames:
        first_frame = output_dir / "frame_000001.jpg"
        scale = f"scale='min({max_width},iw)':-2,format=yuvj420p"
        first_process = subprocess.run(
            ["ffmpeg", "-y", "-i", str(video), "-vf", scale, "-frames:v", "1", str(first_frame)],
            check=False,
            capture_output=True,
            text=True,
        )
        if first_process.returncode != 0:
            raise RuntimeError((first_process.stderr or first_process.stdout or "first-frame ffmpeg failed").strip()[-2000:])
        frames = sorted(output_dir.glob("frame_*.jpg"))
    entries = [
        {"index": index + 1, "time": times[index] if index < len(times) else 0.0, "path": str(frame), "bytes": frame.stat().st_size, "method": "interval"}
        for index, frame in enumerate(frames)
    ]
    data = {"video": str(video), "scene_threshold": None, "fallback_interval": interval, "frames": entries}
    (output_dir.parent / "keyframes.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
