---
name: youtube-reach
description: Operate YouTube through a visible browser for login/search/video/channel/playlist workflows, with yt-dlp public metadata helpers as fallback.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - youtube
      - video
      - retrieval
---

# YouTube Reach

## When to Use

Use this skill when the task needs YouTube video metadata, video explanation, search results, channel or playlist inspection, captions, transcript summaries, visible comments, or source citation from YouTube URLs.

Do not use this skill for generic web search unless the user specifically asks for YouTube content.

## Browser-First Boundary

Use Bamboo's `browser` tool as the primary execution path when login, dynamic search results, comments, channel tabs, age-gated visible pages, or account-visible pages are needed.

Do not read browser cookies, account tokens, local storage, private watch history, or private API credentials directly. Login must happen only through a visible browser window opened by `browser action=open` with `headless=false`; the user completes OAuth/2FA/CAPTCHA manually. If a video is private, region-blocked, deleted, or not visible to the logged-in user, explain the block instead of trying credential extraction.

State-changing actions such as like, subscribe, comment, upload, delete, edit metadata, playlist mutation, or account switch require an explicit final user confirmation after showing the exact target and content.

## Browser Workflows

### Login

1. Open `https://www.youtube.com/` with `browser action=open`, `headless=false`.
2. Ask the user to complete Google login, 2FA, or CAPTCHA in the visible browser.
3. Use `browser action=wait_for_login` with a selector or URL pattern that indicates login has completed.
4. Continue in the same browser session; never copy cookies or tokens into prompts, files, or command arguments.

### Search

1. Open `https://www.youtube.com/results?search_query=<encoded keyword>`.
2. Wait for result cards.
3. Use `browser action=extract_text` or `browser action=eval` to extract visible titles, channels, durations, snippets, and links.
4. Apply filters only through visible controls when the user asks for them.

### Video Explanation

1. Open the video URL in the visible browser.
2. Extract visible title, channel, description, chapter text, visible comments, and available transcript panel text when present.
3. Prefer `transcript` CLI for public captions when available because it is cleaner and easier to cite.
4. If neither browser-visible transcript nor public captions are available, state the limitation and ask for a user-provided media file or approved transcription path.

### Channel or Playlist Analysis

1. Open the channel or playlist URL in the visible browser.
2. Extract visible tabs, video cards, titles, dates, durations, and public stats.
3. Sample a bounded number of visible items and summarize themes, cadence, formats, and audience assumptions.
4. Clearly mark gaps when pagination, login, private videos, or region restrictions hide data.

## Requirements

Preferred backend: `yt-dlp`.

Check availability:

```bash
yt-dlp --version
```

## Commands

The bundled helper wraps common public-data operations:

```bash
python3 <skill_dir>/scripts/youtube_cli.py info "https://www.youtube.com/watch?v=VIDEO_ID"
python3 <skill_dir>/scripts/youtube_cli.py transcript "https://www.youtube.com/watch?v=VIDEO_ID" --languages en,zh-Hans
python3 <skill_dir>/scripts/youtube_cli.py playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --flat
```

Use `python` instead of `python3` only when `python3` is unavailable and `python --version` reports Python 3.

## CLI Fallback Workflow

1. Load this skill for YouTube-specific tasks.
2. Prefer browser workflows for dynamic or login-dependent tasks.
3. Use `info` for public title, channel, duration, upload date, description, tags, and canonical URL.
4. Use `transcript` when public captions or subtitles are needed. Prefer manually created subtitles over automatic captions when both are present.
5. Use `playlist --flat` for playlist or channel listing tasks to avoid downloading full metadata for every video.
6. Never download media unless the user explicitly asks and permissions allow it.
7. Cite the canonical YouTube URL and state whether transcript text came from manual subtitles or automatic captions when that information is available.

## Failure Handling

If `yt-dlp` is missing, say that YouTube support needs `yt-dlp` and provide the command that failed. If YouTube blocks the request, explain the block rather than trying login cookies.
