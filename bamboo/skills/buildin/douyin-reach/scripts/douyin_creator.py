"""Creator, account, and collection helpers for douyin-reach."""

from __future__ import annotations

import re
from typing import Any

from douyin_common import (
    canonical_user_url,
    extract_collection_id,
    extract_user_id,
    fetch_html,
    is_douyin_url,
    looks_like_risk_control,
    parse_metadata,
)

VIDEO_LINK_RE = re.compile(r"https?://www\.douyin\.com/video/\d+|/video/\d+")


def creator_profile(url: str) -> dict[str, Any]:
    if not is_douyin_url(url):
        raise ValueError("expected a Douyin creator URL")
    final_url, raw_html = fetch_html(url)
    parser = parse_metadata(raw_html)
    user_id = extract_user_id(final_url) or extract_user_id(url) or extract_user_id(raw_html)
    return {
        "input_url": url,
        "final_url": final_url,
        "user_id": user_id,
        "canonical_url": canonical_user_url(user_id) if user_id else parser.links.get("canonical", ""),
        "title": parser.meta.get("og:title") or parser.title,
        "description": parser.meta.get("description") or parser.meta.get("og:description") or "",
        "og": {
            "title": parser.meta.get("og:title", ""),
            "description": parser.meta.get("og:description", ""),
            "image": parser.meta.get("og:image", ""),
            "url": parser.meta.get("og:url", ""),
        },
        "visible_video_links": _visible_video_links(raw_html),
        "risk_control_detected": looks_like_risk_control(raw_html),
    }


def collection_list(url: str, *, max_results: int = 30) -> dict[str, Any]:
    if not is_douyin_url(url):
        raise ValueError("expected a Douyin collection URL")
    final_url, raw_html = fetch_html(url)
    parser = parse_metadata(raw_html)
    collection_id = extract_collection_id(final_url) or extract_collection_id(url) or extract_collection_id(raw_html)
    links = _visible_video_links(raw_html)[: max(1, min(max_results, 100))]
    return {
        "input_url": url,
        "final_url": final_url,
        "collection_id": collection_id,
        "title": parser.meta.get("og:title") or parser.title,
        "description": parser.meta.get("description") or parser.meta.get("og:description") or "",
        "visible_video_links": links,
        "visible_count": len(links),
        "risk_control_detected": looks_like_risk_control(raw_html),
    }


def creator_analyze_plan(url: str, *, sample_size: int = 12) -> dict[str, Any]:
    profile = creator_profile(url)
    links = profile.get("visible_video_links", [])
    sample = links[: max(1, min(sample_size, 50))] if isinstance(links, list) else []
    return {
        "profile": profile,
        "sample_video_links": sample,
        "analysis_plan": [
            "Collect recent public video metadata for the sampled links.",
            "For each video, extract title, description, cover, media candidates, transcript if available, and risk-control status.",
            "Cluster topics by title/description/transcript.",
            "Summarize hooks, formats, update rhythm, audience assumptions, and recurring calls to action.",
            "Clearly mark gaps when public pages do not expose complete video lists or metrics.",
        ],
        "requires_browser_when": [
            "The public page hides the creator's video list.",
            "Douyin returns login, CAPTCHA, or risk-control content.",
            "The user asks for logged-in creator-center analytics.",
        ],
    }


def _visible_video_links(raw_html: str) -> list[str]:
    links: list[str] = []
    for match in VIDEO_LINK_RE.findall(raw_html):
        link = match if match.startswith("http") else f"https://www.douyin.com{match}"
        if link not in links:
            links.append(link)
    return links
