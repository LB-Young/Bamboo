#!/usr/bin/env python3
"""Run the full local video insight pipeline: audio, transcript, and keyframes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    parser = argparse.ArgumentParser(description="Extract audio, transcript, and keyframes from a local video.")
    parser.add_argument("video")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--model-dir", default=os.environ.get("VIDEO_INSIGHT_MODEL_DIR"))
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--language")
    parser.add_argument("--skip-transcript", action="store_true")
    parser.add_argument("--skip-keyframes", action="store_true")
    parser.add_argument("--skip-vision", action="store_true")
    parser.add_argument("--skip-ocr", action="store_true")
    parser.add_argument("--scene-threshold", type=float, default=0.35)
    parser.add_argument("--vision-model-dir", default=os.environ.get("VIDEO_INSIGHT_VISION_MODEL_DIR", ""))
    parser.add_argument("--vision-device", default=os.environ.get("VIDEO_INSIGHT_VISION_DEVICE", "auto"))
    parser.add_argument("--vision-dtype", default=os.environ.get("VIDEO_INSIGHT_VISION_DTYPE", "auto"))
    parser.add_argument("--vision-max-new-tokens", type=int, default=int(os.environ.get("VIDEO_INSIGHT_VISION_MAX_NEW_TOKENS", "512")))
    parser.add_argument("--max-vision-frames", type=int, default=int(os.environ.get("VIDEO_INSIGHT_MAX_VISION_FRAMES", "12")))
    args = parser.parse_args(argv)

    try:
        result = process_video(args)
    except RuntimeError as exc:
        print(f"Video insight error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def process_video(args: argparse.Namespace) -> dict[str, Any]:
    script_dir = Path(__file__).resolve().parent
    video = Path(args.video)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audio = output_dir / "audio.wav"

    report: dict[str, Any] = {"video": str(video), "output_dir": str(output_dir)}
    report["audio"] = _run_json([sys.executable, str(script_dir / "extract_audio.py"), str(video), "--output", str(audio)])

    if not args.skip_transcript:
        command = [
            sys.executable,
            str(script_dir / "transcribe_audio.py"),
            str(audio),
            "--output-dir",
            str(output_dir),
            "--model",
            args.model,
            "--device",
            args.device,
            "--compute-type",
            args.compute_type,
        ]
        if args.model_dir:
            command.extend(["--model-dir", args.model_dir])
        if args.language:
            command.extend(["--language", args.language])
        report["transcript"] = _run_json(command)

    if not args.skip_keyframes:
        report["keyframes"] = _run_json(
            [
                sys.executable,
                str(script_dir / "extract_keyframes.py"),
                str(video),
                "--output-dir",
                str(output_dir / "keyframes"),
                "--scene-threshold",
                str(args.scene_threshold),
            ]
        )
        if not args.skip_vision:
            command = [
                sys.executable,
                str(script_dir / "analyze_keyframes.py"),
                "--keyframes-json",
                str(output_dir / "keyframes.json"),
                "--output",
                str(output_dir / "keyframe_analysis.json"),
                "--max-frames",
                str(args.max_vision_frames),
                "--vision-device",
                args.vision_device,
                "--vision-dtype",
                args.vision_dtype,
                "--max-new-tokens",
                str(args.vision_max_new_tokens),
            ]
            if args.vision_model_dir:
                command.extend(["--vision-model-dir", args.vision_model_dir])
            if args.skip_ocr:
                command.append("--skip-ocr")
            analysis_result, analysis_error = _run_optional_json(command)
            if analysis_result is not None:
                report["keyframe_analysis"] = analysis_result
            else:
                report["keyframe_analysis_error"] = analysis_error

    report_path = output_dir / "report.json"
    report["report"] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


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


def _run_json(command: list[str]) -> dict[str, Any]:
    process = subprocess.run(command, check=False, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError((process.stderr or process.stdout or f"command failed: {command}").strip()[-2000:])
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command returned invalid JSON: {' '.join(command)}") from exc


def _run_optional_json(command: list[str]) -> tuple[dict[str, Any] | None, str]:
    process = subprocess.run(command, check=False, capture_output=True, text=True)
    if process.returncode != 0:
        return None, _error_summary(process.stderr or process.stdout or f"command failed: {command}")
    try:
        return json.loads(process.stdout), ""
    except json.JSONDecodeError:
        return None, f"command returned invalid JSON: {' '.join(command)}"


def _error_summary(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("Video insight error:"):
            return line
    return "\n".join(lines[-12:])[-2000:]


if __name__ == "__main__":
    raise SystemExit(main())
