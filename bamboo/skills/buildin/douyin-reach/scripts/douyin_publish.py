"""Guarded publish planning helpers for douyin-reach."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def publish_plan(
    *,
    title: str,
    body: str = "",
    media: list[str] | None = None,
    tags: list[str] | None = None,
    account: str = "",
) -> dict[str, Any]:
    media_items = [_media_item(path) for path in media or []]
    return {
        "operation": "douyin_publish_plan",
        "account": account,
        "title": title,
        "body": body,
        "tags": tags or [],
        "media": media_items,
        "state_changing": True,
        "can_auto_publish": False,
        "requires_visible_browser": True,
        "requires_final_user_confirmation": True,
        "checklist": [
            "Confirm the target Douyin account.",
            "Open Douyin creator center in a visible browser.",
            "Let the user complete login, CAPTCHA, SMS, or risk-control checks manually.",
            "Upload media and fill title/body/tags as a draft.",
            "Show the final preview to the user.",
            "Click publish only after explicit final confirmation.",
        ],
    }


def guarded_workflow() -> dict[str, Any]:
    return {
        "safe_public": ["parse", "resolve", "page", "search-url", "video-info", "capability"],
        "media_download": ["download", "extract-audio", "transcript", "explain-file"],
        "browser_guarded": ["creator-profile", "collection-list", "creator-analyze"],
        "state_changing": ["publish-plan followed by manual visible-browser publish"],
        "never_silent": ["login", "publish", "like", "favorite", "share", "account-switch"],
    }


def _media_item(path: str) -> dict[str, Any]:
    source = Path(path).expanduser()
    return {
        "path": str(source),
        "exists": source.exists(),
        "bytes": source.stat().st_size if source.is_file() else 0,
        "suffix": source.suffix.lower(),
    }
