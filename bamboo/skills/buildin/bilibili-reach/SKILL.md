---
name: bilibili-reach
description: Operate Bilibili through a visible browser for login/search/video/creator workflows, with public CLI helpers as a fallback.
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

Use this skill when the task needs Bilibili search results, video explanation, metadata, creator pages, collections, comments visible in the logged-in browser, or canonical Bilibili links.

Do not use this skill for YouTube or generic video tasks.

## Browser-First Boundary

Use Bamboo's `browser` tool as the primary execution path when login, search result inspection, comments, creator pages, favorites, history, or dynamic page content is needed.

Do not read browser cookies, local storage, QR-login state, or account tokens directly. Login must happen only through a visible browser window opened by `browser action=open` with `headless=false`; the user completes QR/SMS/CAPTCHA manually. If Bilibili returns rate limits, 412 risk-control responses, or login-required data, use `browser action=wait_for_login` or ask the user for visible-browser approval instead of trying credential extraction.

State-changing actions such as like, favorite, coin, follow, comment, danmaku, upload, delete, or account switch require an explicit final user confirmation after showing the exact target and content.

## Browser Workflows

### Login

1. Open `https://www.bilibili.com/` with `browser action=open`, `headless=false`.
2. Ask the user to complete QR/SMS/CAPTCHA in the visible browser.
3. Use `browser action=wait_for_login` with a selector or URL pattern that indicates login has completed.
4. Continue in the same browser session; never copy cookies or tokens into prompts, files, or command arguments.

### Search

1. Open `https://search.bilibili.com/all?keyword=<encoded keyword>`.
2. Wait for result cards.
3. Use `browser action=extract_text` for the main result area.
4. If ranking, filters, or sorting matter, use visible controls with `click/type/press` and extract again.

### Video Explanation

1. Open the video URL in the visible browser.
2. Extract title, uploader, description, stats, chapter/page list, visible comments, and visible transcript/subtitle text when available.
3. If the user asks for the video content itself and no subtitles are visible, state the limitation and ask for a media file or approved download/transcription path.

### Creator or Collection Analysis

1. Open creator space or collection URL.
2. Extract visible profile fields, tabs, recent video cards, titles, dates, and stats.
3. Sample a small number of visible videos and summarize patterns; clearly mark gaps caused by pagination, login walls, or risk control.

## Commands

The bundled helper uses public Bilibili endpoints:

```bash
python3 <skill_dir>/scripts/bilibili_cli.py search "keyword" --max-results 10
python3 <skill_dir>/scripts/bilibili_cli.py video BV1xx411c7mD
python3 <skill_dir>/scripts/bilibili_cli.py video "https://www.bilibili.com/video/BV1xx411c7mD"
```

Use `python` instead of `python3` only when `python3` is unavailable and `python --version` reports Python 3.

## CLI Fallback Workflow

1. Load this skill for Bilibili-specific requests.
2. Prefer browser workflows for dynamic or login-dependent tasks.
3. Use `search` for public keyword discovery when browser automation is unavailable.
4. Use `video` for one known BV id or URL to get title, owner, description, duration, stats, and pages.
5. Keep final answers grounded in returned public URLs and timestamps.
6. Do not claim access to danmaku, paid content, private playlists, or account-only data unless the command result explicitly contains it.

## Failure Handling

If public endpoints fail or return risk-control responses, report the status and suggest trying later or using a user-provided public URL. Do not bypass rate limits.
