"""Public URL and metadata commands for douyin-reach."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from douyin_common import (
    canonical_user_url,
    canonical_video_url,
    clean_url,
    extract_collection_id,
    extract_urls,
    extract_user_id,
    extract_video_id,
    fetch_html,
    is_douyin_url,
    looks_like_risk_control,
    parse_metadata,
    resolve_public_url,
)

MEDIA_URL_RE = re.compile(r"https?:\\/\\/[^\"]+\\.(?:mp4|m3u8)[^\"]*|https?://[^\"'<>]+\\.(?:mp4|m3u8)[^\"'<>]*")
VIDEO_LINK_RE = re.compile(r"https?://www\.douyin\.com/video/\d+")


def parse_text(text: str) -> dict[str, Any]:
    urls = extract_urls(text)
    douyin_urls = [url for url in urls if is_douyin_url(url)]
    search_space = [*douyin_urls, text]
    video_ids = sorted({video_id for value in search_space if (video_id := extract_video_id(value))})
    user_ids = sorted({user_id for value in search_space if (user_id := extract_user_id(value))})
    collection_ids = sorted({item_id for value in search_space if (item_id := extract_collection_id(value))})
    return {
        "urls": douyin_urls,
        "video_ids": video_ids,
        "user_ids": user_ids,
        "collection_ids": collection_ids,
        "canonical_video_urls": [canonical_video_url(video_id) for video_id in video_ids],
        "canonical_user_urls": [canonical_user_url(user_id) for user_id in user_ids],
    }


def resolve_url(url: str) -> dict[str, Any]:
    cleaned = clean_url(url)
    if not is_douyin_url(cleaned):
        return {"input_url": cleaned, "final_url": "", "supported": False, "reason": "expected a Douyin URL"}
    final_url = resolve_public_url(cleaned)
    return {
        "input_url": cleaned,
        "final_url": final_url,
        "video_id": extract_video_id(final_url) or extract_video_id(cleaned),
        "user_id": extract_user_id(final_url) or extract_user_id(cleaned),
        "collection_id": extract_collection_id(final_url) or extract_collection_id(cleaned),
    }


def page_metadata(url: str) -> dict[str, Any]:
    cleaned = clean_url(url)
    if not is_douyin_url(cleaned):
        raise ValueError("expected a Douyin URL")
    final_url, raw_html = fetch_html(cleaned)
    parser = parse_metadata(raw_html)
    video_id = extract_video_id(final_url) or extract_video_id(cleaned) or extract_video_id(raw_html)
    user_id = extract_user_id(final_url) or extract_user_id(cleaned) or extract_user_id(raw_html)
    collection_id = extract_collection_id(final_url) or extract_collection_id(cleaned) or extract_collection_id(raw_html)
    media_candidates = extract_media_candidates(raw_html)
    video_links = sorted(set(VIDEO_LINK_RE.findall(raw_html)))
    return {
        "input_url": cleaned,
        "final_url": final_url,
        "video_id": video_id,
        "user_id": user_id,
        "collection_id": collection_id,
        "canonical_url": canonical_video_url(video_id) if video_id else parser.links.get("canonical", ""),
        "title": parser.meta.get("og:title") or parser.title,
        "description": parser.meta.get("description") or parser.meta.get("og:description") or "",
        "og": {
            "title": parser.meta.get("og:title", ""),
            "description": parser.meta.get("og:description", ""),
            "image": parser.meta.get("og:image", ""),
            "url": parser.meta.get("og:url", ""),
            "video": parser.meta.get("og:video") or parser.meta.get("og:video:url") or "",
        },
        "media_candidates": media_candidates[:10],
        "video_links": video_links[:50],
        "risk_control_detected": looks_like_risk_control(raw_html),
        "public_html_bytes": len(raw_html.encode("utf-8")),
    }


def search_url(query: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(query)
    return {"query": query, "url": f"https://www.douyin.com/search/{encoded}"}


def extract_media_candidates(raw_html: str) -> list[str]:
    candidates: list[str] = []
    for match in MEDIA_URL_RE.findall(raw_html):
        url = match.replace("\\u002F", "/").replace("\\/", "/")
        if url not in candidates:
            candidates.append(url)
    return candidates
