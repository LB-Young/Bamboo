---
name: douyin-reach
description: Parse Douyin share links, inspect public Douyin page metadata, build search URLs, and handle Douyin capability boundaries without reading cookies by default.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - douyin
      - short-video
      - social
      - retrieval
---

# Douyin Reach

## When to Use

Use this skill when the task needs Douyin public video links, short-link resolution, public page metadata, search links, or a safe plan for Douyin web operations.

Do not use this skill for Bilibili, YouTube, Xiaohongshu, Zhihu, or generic web search tasks.

## Capability Model

This Bamboo skill integrates the useful parts of two public Douyin skill approaches:

- Link/video metadata workflows: parse short links and full video URLs, inspect public page metadata, and avoid downloads unless a public media URL is explicitly available.
- Web automation workflows: recognize that login, search, publishing, liking, favoriting, and sharing are browser-state operations that require explicit user approval and may hit platform verification.

The built-in helper only implements stable public operations. Account-changing operations are documented as guarded browser workflows, not executed by this script.

## Privacy Boundary

Use public URLs and public HTML only by default. Do not read browser cookies, local storage, QR-login state, account tokens, or private API credentials. Do not bypass CAPTCHA, login walls, rate limits, or risk-control pages.

Publishing, liking, favoriting, sharing, login, SMS verification, and account switching are account-state operations. They require explicit user authorization, visible-browser review when needed, and final confirmation before any state-changing action.

## Commands

The bundled helper supports safe public URL workflows:

```bash
python3 <skill_dir>/scripts/douyin_cli.py parse "share text or Douyin URL"
python3 <skill_dir>/scripts/douyin_cli.py page "https://www.douyin.com/video/..."
python3 <skill_dir>/scripts/douyin_cli.py search-url "keyword"
python3 <skill_dir>/scripts/douyin_cli.py capability
```

Use `python` instead of `python3` only when `python3` is unavailable and `python --version` reports Python 3.

## Workflow

1. Load this skill for Douyin-specific requests.
2. Use `parse` first when the user pasted share text or a short link; return extracted URLs, detected video ids, user ids, and canonical video links.
3. Use `page` for a known public Douyin URL to fetch and summarize public page metadata such as title, description, canonical URL, OpenGraph fields, final URL, detected video id, and risk-control markers.
4. Use `search-url` when the user needs a Douyin search link for a keyword and public search fetching is not required.
5. Use `capability` when deciding whether a requested operation is supported by the safe helper or requires a guarded browser workflow.
6. Keep final answers grounded in command output and public URLs.
7. Do not claim access to comments, private videos, creator-center data, logged-in search results, downloadable video files, or account-only data unless the command result explicitly contains it.

## Guarded Browser Workflows

These operations are not performed by `douyin_cli.py` and must be treated as separate, explicit browser workflows:

- Login status check, QR login, SMS verification, account switching.
- Searching inside the logged-in Douyin web UI.
- Publishing image posts or videos.
- Liking, favoriting, or sharing from an account.

Before any state-changing operation:

1. Confirm the requested account and action with the user.
2. Prefer a visible browser window if login, CAPTCHA, or risk control appears.
3. Ask the user to complete verification manually.
4. For publishing, require a final visible review of title, body, media, cover, music, and target account before clicking publish.

## Failure Handling

If public pages fail, redirect to a login wall, or return risk-control content, report the status and ask for a public URL or pasted public content. Do not bypass rate limits, CAPTCHA, or login requirements.
