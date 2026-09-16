#!/usr/bin/env python3
"""Transcribe local audio with faster-whisper and write JSON/SRT/VTT outputs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    parser = argparse.ArgumentParser(description="Transcribe local audio with faster-whisper.")
    parser.add_argument("audio")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--model-dir", default=os.environ.get("VIDEO_INSIGHT_MODEL_DIR"))
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--language")
    parser.add_argument("--beam-size", type=int, default=5)
    args = parser.parse_args(argv)

    try:
        result = transcribe_audio(
            Path(args.audio),
            Path(args.output_dir),
            model_name=args.model,
            model_dir=Path(args.model_dir).expanduser() if args.model_dir else None,
            device=args.device,
            compute_type=args.compute_type,
            language=args.language,
            beam_size=args.beam_size,
        )
    except RuntimeError as exc:
        print(f"Video insight error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


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


def transcribe_audio(
    audio: Path,
    output_dir: Path,
    *,
    model_name: str,
    model_dir: Path | None,
    device: str,
    compute_type: str,
    language: str | None,
    beam_size: int,
) -> dict[str, Any]:
    if not audio.is_file():
        raise RuntimeError(f"audio file not found: {audio}")
    try:
        from faster_whisper import WhisperModel
    except ModuleNotFoundError as exc:
        raise RuntimeError("missing optional dependency: install faster-whisper to transcribe audio") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_device = "cuda" if device == "auto" else device
    model_kwargs: dict[str, Any] = {"device": resolved_device, "compute_type": compute_type}
    if model_dir:
        model_dir.mkdir(parents=True, exist_ok=True)
        model_kwargs["download_root"] = str(model_dir)
    model = WhisperModel(model_name, **model_kwargs)
    segments_iter, info = model.transcribe(str(audio), beam_size=beam_size, language=language)
    segments = [
        {"id": index, "start": segment.start, "end": segment.end, "text": segment.text.strip()}
        for index, segment in enumerate(segments_iter, start=1)
    ]
    data = {
        "audio": str(audio),
        "model": model_name,
        "model_dir": str(model_dir) if model_dir else None,
        "device": resolved_device,
        "compute_type": compute_type,
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "segments": segments,
    }
    (output_dir / "transcript.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "transcript.srt").write_text(_to_srt(segments), encoding="utf-8")
    (output_dir / "transcript.vtt").write_text(_to_vtt(segments), encoding="utf-8")
    return data


def _to_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for segment in segments:
        blocks.append(
            f"{segment['id']}\n{_format_srt_time(segment['start'])} --> {_format_srt_time(segment['end'])}\n{segment['text']}\n"
        )
    return "\n".join(blocks)


def _to_vtt(segments: list[dict[str, Any]]) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.extend([f"{_format_vtt_time(segment['start'])} --> {_format_vtt_time(segment['end'])}", segment["text"], ""])
    return "\n".join(lines)


def _format_srt_time(value: float) -> str:
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    return f"{int(hours):02d}:{int(minutes):02d}:{whole:02d},{millis:03d}"


def _format_vtt_time(value: float) -> str:
    return _format_srt_time(value).replace(",", ".")


if __name__ == "__main__":
    raise SystemExit(main())
