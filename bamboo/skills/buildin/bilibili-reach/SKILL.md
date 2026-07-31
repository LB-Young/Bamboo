---
name: bilibili-reach
description: Search public Bilibili videos and inspect public video metadata without reading browser cookies by default.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - bilibili
      - video
      - retrieval
---

# Bilibili Reach

## When to Use

Use this skill when the task needs public Bilibili search results, Bilibili video metadata, creator names, stats, descriptions, or canonical Bilibili links.

Do not use this skill for YouTube or generic video tasks.

## Privacy Boundary

Use public API responses by default. Do not read browser cookies, QR-login state, or account tokens. If Bilibili returns rate limits, 412 risk-control responses, or login-required data, explain the block instead of trying account access.

## Commands

The bundled helper uses public Bilibili endpoints:

```bash
python3 <skill_dir>/scripts/bilibili_cli.py search "keyword" --max-results 10
python3 <skill_dir>/scripts/bilibili_cli.py video BV1xx411c7mD
python3 <skill_dir>/scripts/bilibili_cli.py video "https://www.bilibili.com/video/BV1xx411c7mD"
```

Use `python` instead of `python3` only when `python3` is unavailable and `python --version` reports Python 3.

## Workflow

1. Load this skill for Bilibili-specific requests.
2. Use `search` for keyword discovery and return titles, author, duration, publish time, BV id, and URL.
3. Use `video` for one known BV id or URL to get title, owner, description, duration, stats, and pages.
4. Keep final answers grounded in returned public URLs and timestamps.
5. Do not claim access to danmaku, paid content, private playlists, or account-only data unless the command result explicitly contains it.

## Failure Handling

If public endpoints fail or return risk-control responses, report the status and suggest trying later or using a user-provided public URL. Do not bypass rate limits.
