#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from bamboo.helpers.config import load_builtin_skill_variables

DEFAULT_BASE_URL = "https://redfox.hk"


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def load_api_key(skill_name: str) -> str:
    variables = load_builtin_skill_variables(skill_name)
    api_key = os.environ.get("REDFOX_API_KEY") or str(variables.get("REDFOX_API_KEY") or "")
    if not api_key:
        raise RedFoxHubError("missing REDFOX_API_KEY; set it in the environment or the built-in skill variables")
    return api_key


def base_url(skill_name: str) -> str:
    variables = load_builtin_skill_variables(skill_name)
    return (
        os.environ.get("REDFOX_BASE_URL")
        or str(variables.get("REDFOX_BASE_URL") or DEFAULT_BASE_URL)
    ).rstrip("/")


def post(skill_name: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request(skill_name, "POST", path, payload=payload)


def get(skill_name: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
    return _request(skill_name, "GET", path, params=params)


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def handle_cli(func) -> int:
    try:
        print_json(func())
        return 0
    except RedFoxHubError as exc:
        print(f"RedFoxHub error: {exc}", file=sys.stderr)
        return 1


def compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "")}


def _request(
    skill_name: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_key = load_api_key(skill_name)
    url = f"{base_url(skill_name)}{path}"
    data = None
    if method == "POST":
        data = json.dumps(compact_payload(payload or {}), ensure_ascii=False).encode("utf-8")
    elif params:
        query = urllib.parse.urlencode(compact_payload(params), doseq=True)
        url = f"{url}?{query}"

    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Bamboo RedFoxHub Reach/1",
            "REDFOX_API_KEY": api_key,
            "X-API-KEY": api_key,
            "X-API-Key": api_key,
            "REDFOX-API-KEY": api_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RedFoxHubError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RedFoxHubError(f"network failure: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RedFoxHubError(f"invalid JSON response from HTTP {status}: {raw[:500]}") from exc

    code = parsed.get("code") if isinstance(parsed, dict) else None
    if code not in (None, 0, 2000, "0", "2000"):
        message = parsed.get("msg") or parsed.get("message") or "unknown RedFoxHub error"
        raise RedFoxHubError(f"code={code}: {message}")
    return {
        "source": "RedFoxHub",
        "method": method,
        "path": path,
        "data": parsed.get("data", parsed) if isinstance(parsed, dict) else parsed,
    }

import argparse
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SKILL = "xiaohongshu-reach"
PATH = "/story/api/parseWork/parse"


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse and optionally download a Xiaohongshu video through RedFoxHub.")
    parser.add_argument("url")
    parser.add_argument("--output-dir", help="Download the first parsed video candidate into this directory.")
    parser.add_argument("--filename", help="Optional output filename when --output-dir is set.")
    parser.add_argument("--max-bytes", type=int, default=500 * 1024 * 1024)
    args = parser.parse_args()

    def run() -> dict[str, Any]:
        result = post(SKILL, PATH, {"url": args.url})
        candidates = _video_candidates(result.get("data"))
        output = {**result, "video_candidates": candidates}
        if args.output_dir:
            if not candidates:
                raise RedFoxHubError("RedFoxHub returned no downloadable video URL candidates")
            output["downloaded"] = _download(candidates[0]["url"], Path(args.output_dir), args.filename, args.max_bytes)
        return output

    return handle_cli(run)


def _video_candidates(value: Any) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")
        elif isinstance(node, str) and node.startswith(("http://", "https://")):
            lowered = node.lower()
            score = int(any(token in lowered for token in (".mp4", ".mov", ".m4v", ".webm", "video", "play")))
            if score and node not in seen:
                seen.add(node)
                candidates.append({"url": node, "field": path})

    walk(value, "")
    candidates.sort(key=lambda item: (".m3u8" in item["url"].lower(), item["field"]))
    return candidates


def _download(url: str, output_dir: Path, filename: str | None, max_bytes: int) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / (filename or _filename_from_url(url))
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RedFoxHubError(f"download exceeds --max-bytes ({max_bytes})")
                handle.write(chunk)
    except OSError as exc:
        raise RedFoxHubError(f"download failed: {exc}") from exc
    return {"path": str(target), "bytes": total, "url": url}


def _filename_from_url(url: str) -> str:
    name = Path(urllib.parse.urlparse(url).path).name or "video.mp4"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name if "." in name else f"{name}.mp4"


if __name__ == "__main__":
    raise SystemExit(main())
