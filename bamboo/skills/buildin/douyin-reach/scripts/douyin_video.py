"""Video inspection, download, and local media helpers for douyin-reach."""

from __future__ import annotations

import mimetypes
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from douyin_common import DouyinError, canonical_video_url, download_dir, max_download_bytes, request_headers
from douyin_public import page_metadata

TRANSCRIPT_SUFFIXES = (".srt", ".vtt", ".txt")


def video_info(url: str) -> dict[str, Any]:
    metadata = page_metadata(url)
    return {
        "video_id": metadata.get("video_id"),
        "canonical_url": metadata.get("canonical_url"),
        "final_url": metadata.get("final_url"),
        "title": metadata.get("title"),
        "description": metadata.get("description"),
        "cover": metadata.get("og", {}).get("image") if isinstance(metadata.get("og"), dict) else "",
        "public_media_candidates": metadata.get("media_candidates", []),
        "risk_control_detected": metadata.get("risk_control_detected", False),
        "notes": [
            "Douyin does not consistently expose captions in public HTML.",
            "If no media candidate is returned, use a guarded browser workflow or a user-provided video file.",
        ],
    }


def download_public_media(url: str, *, output_dir: str | None = None, media_url: str = "") -> dict[str, Any]:
    source_url = media_url
    metadata: dict[str, Any] = {}
    if not source_url:
        metadata = page_metadata(url)
        candidates = metadata.get("media_candidates", [])
        source_url = str(candidates[0]) if candidates else ""
    if not source_url:
        raise DouyinError("no public media URL found; use a user-provided media URL or guarded browser workflow")
    target_dir = Path(output_dir).expanduser() if output_dir else download_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = _suffix_for_url(source_url) or ".mp4"
    video_id = str(metadata.get("video_id") or "").strip()
    filename = f"douyin-{video_id}{suffix}" if video_id else f"douyin-media{suffix}"
    target = _unique_path(target_dir / filename)
    bytes_written = _download_to_file(source_url, target)
    return {
        "source_url": source_url,
        "output_path": str(target),
        "bytes": bytes_written,
        "video_id": video_id,
        "canonical_url": canonical_video_url(video_id) if video_id else "",
    }


def extract_audio(video_path: str, *, output_path: str = "") -> dict[str, Any]:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise DouyinError("ffmpeg is not installed or not on PATH")
    source = Path(video_path).expanduser()
    if not source.is_file():
        raise DouyinError(f"video file not found: {source}")
    target = Path(output_path).expanduser() if output_path else source.with_suffix(".m4a")
    command = [executable, "-y", "-i", str(source), "-vn", "-acodec", "copy", str(target)]
    process = subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)
    if process.returncode != 0:
        command = [executable, "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(target.with_suffix(".wav"))]
        process = subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)
        target = target.with_suffix(".wav")
    if process.returncode != 0:
        raise DouyinError((process.stderr or process.stdout or "ffmpeg failed").strip()[:1000])
    return {"input_path": str(source), "audio_path": str(target), "bytes": target.stat().st_size}


def transcript(video_or_transcript_path: str) -> dict[str, Any]:
    source = Path(video_or_transcript_path).expanduser()
    if not source.exists():
        raise DouyinError(f"file not found: {source}")
    transcript_path = _find_transcript_file(source)
    if transcript_path is None:
        return {
            "input_path": str(source),
            "transcript_path": "",
            "text": "",
            "available": False,
            "next_step": "Extract audio and run Bamboo's configured speech-to-text capability or provide a transcript file.",
        }
    text = transcript_path.read_text(encoding="utf-8", errors="replace")
    return {
        "input_path": str(source),
        "transcript_path": str(transcript_path),
        "text": text,
        "available": True,
        "chars": len(text),
    }


def explain_file(path: str) -> dict[str, Any]:
    source = Path(path).expanduser()
    if not source.is_file():
        raise DouyinError(f"file not found: {source}")
    transcript_data = transcript(str(source))
    guessed_type, _ = mimetypes.guess_type(str(source))
    return {
        "path": str(source),
        "bytes": source.stat().st_size,
        "mime_type": guessed_type or "",
        "transcript_available": transcript_data["available"],
        "transcript_chars": transcript_data.get("chars", 0),
        "analysis_guidance": [
            "Use transcript text for spoken content when available.",
            "If transcript is unavailable, extract audio and run speech-to-text before summarizing claims.",
            "For visual analysis, sample frames with a media tool and inspect representative frames.",
        ],
    }


def _download_to_file(url: str, target: Path) -> int:
    request = urllib.request.Request(url, headers=request_headers())
    limit = max_download_bytes()
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise DouyinError(f"download exceeds configured limit of {limit} bytes")
                output.write(chunk)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise DouyinError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DouyinError(f"network failure: {exc}") from exc
    return written


def _suffix_for_url(url: str) -> str:
    path = Path(url.split("?", 1)[0])
    suffix = path.suffix.lower()
    return suffix if suffix in (".mp4", ".m3u8", ".mov", ".webm") else ""


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise DouyinError(f"cannot allocate output file near {path}")


def _find_transcript_file(source: Path) -> Path | None:
    if source.suffix.lower() in TRANSCRIPT_SUFFIXES:
        return source
    for suffix in TRANSCRIPT_SUFFIXES:
        candidate = source.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    return None
