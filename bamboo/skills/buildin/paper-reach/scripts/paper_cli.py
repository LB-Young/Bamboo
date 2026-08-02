#!/usr/bin/env python3
"""Minimal public paper metadata helper for Bamboo's paper-reach skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from bamboo.helpers.config import load_builtin_skill_variables

ARXIV_API = "https://export.arxiv.org/api/query"
CROSSREF_API = "https://api.crossref.org/works"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
FALLBACK_USER_AGENT = "Bamboo Paper Reach/1"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = args.handler(args)
    except PaperError as exc:
        print(f"Paper reach error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


class PaperError(RuntimeError):
    """Raised when public paper metadata cannot be fetched."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search public paper metadata from arXiv and DOI/Crossref.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    arxiv_search = subparsers.add_parser("arxiv-search", help="Search arXiv by query.")
    arxiv_search.add_argument("query")
    arxiv_search.add_argument("--max-results", type=int, default=5)
    arxiv_search.set_defaults(handler=_cmd_arxiv_search)

    arxiv_id = subparsers.add_parser("arxiv-id", help="Fetch one arXiv record by id.")
    arxiv_id.add_argument("id")
    arxiv_id.set_defaults(handler=_cmd_arxiv_id)

    doi = subparsers.add_parser("doi", help="Fetch Crossref metadata for a DOI.")
    doi.add_argument("doi")
    doi.set_defaults(handler=_cmd_doi)
    return parser


def _cmd_arxiv_search(args: argparse.Namespace) -> dict[str, Any]:
    limit = max(1, min(args.max_results, 20))
    root = _get_xml(ARXIV_API, {"search_query": f"all:{args.query}", "start": "0", "max_results": str(limit)})
    entries = [_arxiv_entry(entry) for entry in root.findall(f"{ATOM}entry")]
    return {"query": args.query, "results": entries}


def _cmd_arxiv_id(args: argparse.Namespace) -> dict[str, Any]:
    root = _get_xml(ARXIV_API, {"id_list": args.id})
    entries = [_arxiv_entry(entry) for entry in root.findall(f"{ATOM}entry")]
    return {"id": args.id, "record": entries[0] if entries else None}


def _cmd_doi(args: argparse.Namespace) -> dict[str, Any]:
    doi = args.doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    data = _get_json(f"{CROSSREF_API}/{urllib.parse.quote(doi, safe='')}")
    message = data.get("message") if isinstance(data, dict) else {}
    if not isinstance(message, dict):
        raise PaperError("Crossref response did not contain metadata")
    return {
        "doi": message.get("DOI") or doi,
        "title": _first(message.get("title")),
        "subtitle": _first(message.get("subtitle")),
        "container_title": _first(message.get("container-title")),
        "publisher": message.get("publisher"),
        "type": message.get("type"),
        "published": _date_parts(message.get("published-print") or message.get("published-online") or message.get("issued")),
        "authors": [_author_name(author) for author in message.get("author", []) if isinstance(author, dict)],
        "url": message.get("URL") or f"https://doi.org/{doi}",
        "reference_count": message.get("reference-count"),
        "is_referenced_by_count": message.get("is-referenced-by-count"),
    }


def _get_xml(url: str, params: dict[str, str]) -> ET.Element:
    raw = _fetch(f"{url}?{urllib.parse.urlencode(params)}")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise PaperError(f"invalid XML response: {exc}") from exc


def _get_json(url: str) -> Any:
    raw = _fetch(url)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PaperError(f"invalid JSON response: {raw[:300]}") from exc


def _fetch(url: str) -> str:
    variables = load_builtin_skill_variables("paper-reach")
    user_agent = os.environ.get("PAPER_REACH_USER_AGENT") or str(
        variables.get("PAPER_REACH_USER_AGENT") or FALLBACK_USER_AGENT
    )
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise PaperError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise PaperError(f"network failure: {exc}") from exc


def _arxiv_entry(entry: ET.Element) -> dict[str, Any]:
    arxiv_id = _text(entry.find(f"{ATOM}id")).rsplit("/", 1)[-1]
    return {
        "id": arxiv_id,
        "title": " ".join(_text(entry.find(f"{ATOM}title")).split()),
        "summary": " ".join(_text(entry.find(f"{ATOM}summary")).split()),
        "published": _text(entry.find(f"{ATOM}published")),
        "updated": _text(entry.find(f"{ATOM}updated")),
        "authors": [_text(author.find(f"{ATOM}name")) for author in entry.findall(f"{ATOM}author")],
        "primary_category": (entry.find(f"{ARXIV}primary_category").attrib.get("term", "") if entry.find(f"{ARXIV}primary_category") is not None else ""),
        "categories": [category.attrib.get("term", "") for category in entry.findall(f"{ATOM}category")],
        "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else _text(entry.find(f"{ATOM}id")),
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
    }


def _text(element: ET.Element | None) -> str:
    return "".join(element.itertext()).strip() if element is not None else ""


def _first(value: object) -> str:
    return str(value[0]) if isinstance(value, list) and value else ""


def _date_parts(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return ""
    return "-".join(str(part) for part in parts[0])


def _author_name(author: dict[str, Any]) -> str:
    given = str(author.get("given") or "").strip()
    family = str(author.get("family") or "").strip()
    literal = str(author.get("name") or "").strip()
    return " ".join(part for part in (given, family) if part) or literal


if __name__ == "__main__":
    raise SystemExit(main())
