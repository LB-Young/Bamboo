---
name: douyin-reach
description: "Work with Douyin as one integrated skill: parse links, resolve short URLs, inspect public metadata, explain/download videos, analyze creators or collections, build search URLs, and plan guarded publishing without reading cookies by default."
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - douyin
      - short-video
      - creator-analysis
      - publishing
      - retrieval
---

# Douyin Reach

## When to Use

Use this skill when the task is about Douyin videos, share links, short links, video explanation, public metadata, creator/account analysis, collection analysis, Douyin search, or guarded content publishing.

Do not use this skill for Bilibili, YouTube, Xiaohongshu, Zhihu, or generic web search tasks.

## Capability Map

This is one Bamboo skill with multiple internal modules:

| Module | Commands | Use for |
| --- | --- | --- |
| Public reach | `parse`, `resolve`, `page`, `search-url` | Share text parsing, short-link resolution, public HTML metadata, safe search links |
| Video understanding | `video-info`, `download`, `extract-audio`, `transcript`, `explain-file` | Single video explanation, public media download, local file inspection, transcript sidecar reading |
| Creator and collection analysis | `creator-profile`, `collection-list`, `creator-analyze` | Public account profile, visible video links, collection metadata, analysis plan |
| Publishing workflow | `publish-plan` | Title/body/tag/media checklist and guarded upload plan |
| Capability routing | `capability` | Decide whether a request is safe, media-download, browser-guarded, or state-changing |

## Safety Levels

- `safe_public`: `parse`, `resolve`, `page`, `search-url`, `video-info`, `capability`.
- `media_download`: `download`, `extract-audio`, `transcript`, `explain-file`. Ask before saving large files or writing outside the current workspace.
- `browser_guarded`: creator pages, collection pages, logged-in search, or any flow that needs a visible browser.
- `state_changing`: publish, like, favorite, share, account switch. Never perform silently.

Use public URLs and public HTML by default. Do not read browser cookies, local storage, QR-login state, account tokens, private APIs, creator-center analytics, or private account data unless the user explicitly authorizes an approved visible-browser workflow. Do not bypass CAPTCHA, login walls, rate limits, or risk-control pages.

## Commands

Run all subcommands through the single bundled entrypoint:

```bash
python3 <skill_dir>/scripts/douyin_cli.py parse "share text or Douyin URL"
python3 <skill_dir>/scripts/douyin_cli.py resolve "https://v.douyin.com/..."
python3 <skill_dir>/scripts/douyin_cli.py page "https://www.douyin.com/video/..."
python3 <skill_dir>/scripts/douyin_cli.py search-url "keyword"

python3 <skill_dir>/scripts/douyin_cli.py video-info "https://www.douyin.com/video/..."
python3 <skill_dir>/scripts/douyin_cli.py download "https://www.douyin.com/video/..." --output-dir ./downloads
python3 <skill_dir>/scripts/douyin_cli.py extract-audio ./video.mp4
python3 <skill_dir>/scripts/douyin_cli.py transcript ./video.mp4
python3 <skill_dir>/scripts/douyin_cli.py explain-file ./video.mp4

python3 <skill_dir>/scripts/douyin_cli.py creator-profile "https://www.douyin.com/user/..."
python3 <skill_dir>/scripts/douyin_cli.py collection-list "https://www.douyin.com/collection/..."
python3 <skill_dir>/scripts/douyin_cli.py creator-analyze "https://www.douyin.com/user/..."

python3 <skill_dir>/scripts/douyin_cli.py publish-plan --title "..." --body "..." --media ./video.mp4 --tag topic
python3 <skill_dir>/scripts/douyin_cli.py capability
```

Use `python` instead of `python3` only when `python3` is unavailable and `python --version` reports Python 3.

## Single Video Workflow

1. Use `parse` for pasted share text or short links.
2. Use `resolve` for short links before deeper analysis.
3. Use `video-info` for public title, description, cover, canonical URL, and media candidates.
4. If a public media candidate exists and the user wants a local copy, use `download`.
5. For explanation:
   - Prefer explicit subtitles or sidecar transcript when available.
   - Use `extract-audio` and Bamboo's speech-to-text capability when transcript is unavailable.
   - Use `explain-file` to collect local file size, MIME type, transcript availability, and analysis guidance.
6. State clearly when Douyin public pages do not expose subtitles, full video URLs, comments, or metrics.

## Creator and Collection Workflow

1. Use `creator-profile` for public account metadata and visible video links.
2. Use `collection-list` for public collection metadata and visible video links.
3. Use `creator-analyze` to generate a structured analysis plan from visible public data.
4. For deeper creator analysis, sample recent visible videos, run `video-info` or local transcript workflows for each, then aggregate topics, hooks, formats, update rhythm, and recurring calls to action.
5. If public pages hide the video list, metrics, or creator-center analytics, stop and explain that a guarded browser workflow is required.

## Search Workflow

Use `search-url` by default to produce a Douyin search URL. Logged-in search result scraping is a browser-guarded workflow and must use a visible browser when login, CAPTCHA, or risk control appears.

## Publishing Workflow

Use `publish-plan` to prepare a publish checklist. The helper does not click publish.

Before any publish/upload action:

1. Confirm target account, title, body, tags, media, cover, and schedule with the user.
2. Use a visible browser for creator center.
3. Let the user complete login, SMS, QR, CAPTCHA, or risk-control checks manually.
4. Fill a draft and show final preview.
5. Click publish only after explicit final user confirmation.

## Failure Handling

If public pages fail, redirect to login, return risk-control content, or hide data, report the status and ask for a public URL, uploaded file, transcript, or visible-browser approval. Do not bypass platform protections.
