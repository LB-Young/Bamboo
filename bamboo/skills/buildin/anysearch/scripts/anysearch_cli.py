#!/usr/bin/env python3
"""Minimal AnySearch JSON-RPC CLI for Bamboo's built-in anysearch skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENDPOINT = "https://api.anysearch.com/mcp"
CLIENT_HEADER = "bamboo-skill/1"
AVAILABLE_DOMAINS = (
    "general",
    "resource",
    "social_media",
    "finance",
    "academic",
    "legal",
    "health",
    "business",
    "security",
    "ip",
    "code",
    "energy",
    "environment",
    "agriculture",
    "travel",
    "film",
    "gaming",
)


def main(argv: list[str] | None = None) -> int:
    _load_env_file()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except AnySearchError as exc:
        print(f"AnySearch error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


class AnySearchError(RuntimeError):
    """Raised when the remote AnySearch API cannot complete a call."""


def _load_env_file() -> None:
    skill_dir = Path(__file__).resolve().parents[1]
    env_path = skill_dir / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and value:
            os.environ[key] = value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search and extract content through the AnySearch API.")
    parser.add_argument("--api-key", default=os.environ.get("ANYSEARCH_API_KEY", ""), help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Run a single web or vertical-domain search.")
    search_parser.add_argument("query")
    search_parser.add_argument("--domain", choices=AVAILABLE_DOMAINS)
    search_parser.add_argument("--sub-domain", "--sub_domain", dest="sub_domain")
    search_parser.add_argument("--sdp", "--sub-domain-params", "--sub_domain_params", dest="sub_domain_params")
    search_parser.add_argument("--max-results", "--max_results", dest="max_results", type=int)
    search_parser.set_defaults(handler=_cmd_search)

    batch_parser = subparsers.add_parser("batch-search", aliases=["batch_search"], help="Run up to five searches.")
    batch_parser.add_argument("--query", action="append", dest="queries", required=True)
    batch_parser.add_argument("--max-results", "--max_results", dest="max_results", type=int)
    batch_parser.set_defaults(handler=_cmd_batch_search)

    extract_parser = subparsers.add_parser("extract", help="Extract a URL as Markdown.")
    extract_parser.add_argument("url", nargs="?")
    extract_parser.add_argument("--url", "-u", dest="url_option")
    extract_parser.set_defaults(handler=_cmd_extract)

    domains_parser = subparsers.add_parser("get-sub-domains", aliases=["get_sub_domains"], help="List vertical sub-domains.")
    domains_parser.add_argument("--domain", choices=AVAILABLE_DOMAINS)
    domains_parser.add_argument("--domains")
    domains_parser.set_defaults(handler=_cmd_get_sub_domains)
    return parser


def _cmd_search(args: argparse.Namespace) -> str:
    payload: dict[str, Any] = {"query": args.query}
    if args.domain:
        payload["domain"] = args.domain
    if args.sub_domain:
        payload["sub_domain"] = args.sub_domain
    if args.sub_domain_params:
        payload["sub_domain_params"] = _parse_params(args.sub_domain_params)
    if args.max_results is not None:
        payload["max_results"] = _clamp_max_results(args.max_results)
    return _call_api("search", payload, args.api_key)


def _cmd_batch_search(args: argparse.Namespace) -> str:
    queries = [{"query": query} for query in args.queries]
    if len(queries) > 5:
        raise AnySearchError("batch-search supports at most 5 queries")
    if args.max_results is not None:
        max_results = _clamp_max_results(args.max_results)
        for query in queries:
            query["max_results"] = max_results
    return _call_api("batch_search", {"queries": queries}, args.api_key)


def _cmd_extract(args: argparse.Namespace) -> str:
    url = args.url or args.url_option
    if not url:
        raise AnySearchError("extract requires a URL")
    return _call_api("extract", {"url": url}, args.api_key)


def _cmd_get_sub_domains(args: argparse.Namespace) -> str:
    if args.domains:
        domains = [domain.strip() for domain in args.domains.split(",") if domain.strip()]
        return _call_api("get_sub_domains", {"domains": domains}, args.api_key)
    if args.domain:
        return _call_api("get_sub_domains", {"domain": args.domain}, args.api_key)
    raise AnySearchError("get-sub-domains requires --domain or --domains")


def _parse_params(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}
        for pair in raw.split(","):
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            key = key.strip()
            if key:
                parsed[key] = value.strip()
    if not isinstance(parsed, dict) or not parsed:
        raise AnySearchError("--sdp must be JSON object text or comma-separated key=value pairs")
    return parsed


def _clamp_max_results(value: int) -> int:
    return max(1, min(value, 10))


def _call_api(tool_name: str, arguments: dict[str, Any], api_key: str) -> str:
    request_body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Anysearch-Client": CLIENT_HEADER,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(ENDPOINT, data=request_body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw_response = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise AnySearchError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AnySearchError(f"network failure: {exc.reason}") from exc
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise AnySearchError(f"invalid JSON response: {raw_response[:500]}") from exc
    if "error" in data:
        error = data["error"]
        message = error.get("message", error) if isinstance(error, dict) else error
        raise AnySearchError(str(message))
    result = data.get("result", {})
    content = result.get("content", []) if isinstance(result, dict) else []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            return str(item.get("text", ""))
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
