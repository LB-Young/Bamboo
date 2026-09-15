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


SKILL = "bilibili-reach"
PATH = "/story/api/bili/data/workSearch"


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Bilibili videos through RedFoxHub.")
    parser.add_argument("keyword")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--order", default="time", choices=["time", "play", "like", "comment", "favorite"])
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {
        "keyword": args.keyword,
        "page": args.page,
        "pageSize": args.page_size,
        "order": args.order,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
