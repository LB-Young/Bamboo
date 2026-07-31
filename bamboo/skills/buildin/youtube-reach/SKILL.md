---
name: youtube-reach
description: Inspect YouTube videos, channels, playlists, metadata, captions, and transcripts using yt-dlp without reading browser cookies by default.
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

Use this skill when the task needs YouTube video metadata, channel or playlist inspection, captions, transcript summaries, or source citation from YouTube URLs.

Do not use this skill for generic web search unless the user specifically asks for YouTube content.

## Privacy Boundary

Do not read browser cookies, account tokens, or private watch history. Use public metadata and public captions by default. If a video is age-gated, private, region-blocked, or requires login, tell the user instead of attempting account-based access.

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

## Workflow

1. Load this skill for YouTube-specific tasks.
2. Use `info` for title, channel, duration, upload date, description, tags, and canonical URL.
3. Use `transcript` when captions or subtitles are needed. Prefer manually created subtitles over automatic captions when both are present.
4. Use `playlist --flat` for playlist or channel listing tasks to avoid downloading full metadata for every video.
5. Never download media unless the user explicitly asks and permissions allow it.
6. Cite the canonical YouTube URL and state whether transcript text came from manual subtitles or automatic captions when that information is available.

## Failure Handling

If `yt-dlp` is missing, say that YouTube support needs `yt-dlp` and provide the command that failed. If YouTube blocks the request, explain the block rather than trying login cookies.
