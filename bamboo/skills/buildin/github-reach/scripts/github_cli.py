#!/usr/bin/env python3
"""Minimal public GitHub helper for Bamboo's github-reach skill."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from bamboo.helpers.config import load_builtin_skill_variables

API_ROOT = "https://api.github.com"
FALLBACK_USER_AGENT = "Bamboo GitHub Reach/1"
REPO_RE = re.compile(r"github\.com[:/](?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)|^(?P<short>[^/\s]+)/([^/\s]+)$")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except GitHubError as exc:
        print(f"GitHub reach error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


class GitHubError(RuntimeError):
    """Raised when a public GitHub request cannot be completed."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect public GitHub metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    repo = subparsers.add_parser("repo", help="Fetch public repository metadata.")
    repo.add_argument("repository", help="owner/repo or GitHub URL.")
    repo.set_defaults(handler=_cmd_repo)

    parse = subparsers.add_parser("parse", help="Parse a GitHub repository URL or owner/repo string.")
    parse.add_argument("repository", help="owner/repo or GitHub URL.")
    parse.set_defaults(handler=_cmd_parse)

    releases = subparsers.add_parser("releases", help="Fetch recent public releases.")
    releases.add_argument("repository")
    releases.add_argument("--max-results", type=int, default=5)
    releases.set_defaults(handler=_cmd_releases)

    issues = subparsers.add_parser("issues", help="Fetch public issues.")
    issues.add_argument("repository")
    issues.add_argument("--state", choices=("open", "closed", "all"), default="open")
    issues.add_argument("--max-results", type=int, default=10)
    issues.set_defaults(handler=_cmd_issues)

    prs = subparsers.add_parser("prs", help="Fetch public pull requests.")
    prs.add_argument("repository")
    prs.add_argument("--state", choices=("open", "closed", "all"), default="open")
    prs.add_argument("--max-results", type=int, default=10)
    prs.set_defaults(handler=_cmd_prs)

    user = subparsers.add_parser("user", help="Fetch public user or organization metadata.")
    user.add_argument("login")
    user.set_defaults(handler=_cmd_user)
    return parser


def _cmd_parse(args: argparse.Namespace) -> dict[str, Any]:
    owner, repo = _parse_repository(args.repository)
    return {
        "owner": owner,
        "repo": repo,
        "full_name": f"{owner}/{repo}",
        "html_url": f"https://github.com/{owner}/{repo}",
    }


def _cmd_repo(args: argparse.Namespace) -> dict[str, Any]:
    owner, repo = _parse_repository(args.repository)
    data = _get_json(f"/repos/{owner}/{repo}")
    return {
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "html_url": data.get("html_url"),
        "homepage": data.get("homepage"),
        "language": data.get("language"),
        "license": (data.get("license") or {}).get("spdx_id") if isinstance(data.get("license"), dict) else None,
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "open_issues": data.get("open_issues_count"),
        "default_branch": data.get("default_branch"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "pushed_at": data.get("pushed_at"),
        "topics": data.get("topics") or [],
    }


def _cmd_releases(args: argparse.Namespace) -> dict[str, Any]:
    owner, repo = _parse_repository(args.repository)
    limit = max(1, min(args.max_results, 30))
    data = _get_json(f"/repos/{owner}/{repo}/releases", {"per_page": str(limit)})
    return {
        "repository": f"{owner}/{repo}",
        "releases": [
            {
                "name": item.get("name"),
                "tag_name": item.get("tag_name"),
                "html_url": item.get("html_url"),
                "published_at": item.get("published_at"),
                "prerelease": item.get("prerelease"),
                "draft": item.get("draft"),
            }
            for item in data
            if isinstance(item, dict)
        ],
    }


def _cmd_issues(args: argparse.Namespace) -> dict[str, Any]:
    return _list_items(args.repository, kind="issues", state=args.state, max_results=args.max_results)


def _cmd_prs(args: argparse.Namespace) -> dict[str, Any]:
    return _list_items(args.repository, kind="pulls", state=args.state, max_results=args.max_results)


def _cmd_user(args: argparse.Namespace) -> dict[str, Any]:
    data = _get_json(f"/users/{args.login}")
    return {
        "login": data.get("login"),
        "name": data.get("name"),
        "type": data.get("type"),
        "html_url": data.get("html_url"),
        "company": data.get("company"),
        "blog": data.get("blog"),
        "location": data.get("location"),
        "public_repos": data.get("public_repos"),
        "followers": data.get("followers"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def _list_items(repository: str, *, kind: str, state: str, max_results: int) -> dict[str, Any]:
    owner, repo = _parse_repository(repository)
    limit = max(1, min(max_results, 50))
    data = _get_json(f"/repos/{owner}/{repo}/{kind}", {"state": state, "per_page": str(limit)})
    return {
        "repository": f"{owner}/{repo}",
        "kind": "pull_requests" if kind == "pulls" else "issues",
        "state": state,
        "items": [
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "html_url": item.get("html_url"),
                "state": item.get("state"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "user": (item.get("user") or {}).get("login") if isinstance(item.get("user"), dict) else None,
            }
            for item in data
            if isinstance(item, dict)
        ],
    }


def _get_json(path: str, params: dict[str, str] | None = None) -> Any:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    variables = load_builtin_skill_variables("github-reach")
    user_agent = os.environ.get("GITHUB_REACH_USER_AGENT") or str(
        variables.get("GITHUB_REACH_USER_AGENT") or FALLBACK_USER_AGENT
    )
    request = urllib.request.Request(
        f"{API_ROOT}{path}{query}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": user_agent},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise GitHubError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GitHubError(f"network failure: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GitHubError(f"invalid JSON response: {raw[:300]}") from exc


def _parse_repository(value: str) -> tuple[str, str]:
    value = value.strip().removesuffix(".git")
    match = REPO_RE.search(value)
    if not match:
        raise GitHubError("expected owner/repo or a GitHub repository URL")
    if match.group("owner"):
        return match.group("owner"), match.group("repo").removesuffix(".git")
    owner, repo = value.split("/", 1)
    return owner, repo.removesuffix(".git")


if __name__ == "__main__":
    raise SystemExit(main())
