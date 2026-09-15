---
name: youtube-reach
description: Query YouTube video search, details, comments, and transcript tasks through RedFoxHub APIs.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - youtube
      - video
      - retrieval
      - redfoxhub
---

# YouTube Reach

## When to Use

Use this skill when the task needs YouTube video search, video details, comments, video download parsing, or transcript extraction through RedFoxHub.

Do not use this skill for direct YouTube browser automation, Google login, private videos, subscriptions, playlists, uploading, liking, or channel management.

## Authentication

All scripts call RedFoxHub and require `REDFOX_API_KEY`.

```bash
export REDFOX_API_KEY="ak_xxxx"
```

The optional `REDFOX_BASE_URL` overrides the default host `https://redfox.hk`.

## Scripts

```bash
python <skill_dir>/scripts/search_videos.py "AI tutorial"
python <skill_dir>/scripts/search_videos.py "AI tutorial" --continuation-token "token_from_previous_page"
python <skill_dir>/scripts/get_video.py "VIDEO_ID_OR_URL"
python <skill_dir>/scripts/comments.py "VIDEO_ID" --continuation-token "optional_token"
python <skill_dir>/scripts/download_video.py "https://www.youtube.com/watch?v=VIDEO_ID"
python <skill_dir>/scripts/download_video.py "https://www.youtube.com/watch?v=VIDEO_ID" --output-dir ./downloads
python <skill_dir>/scripts/transcript.py submit "https://www.youtube.com/watch?v=VIDEO_ID"
python <skill_dir>/scripts/transcript.py result "task_id_from_submit"
```

## Capability Notes

- `search_videos.py` calls RedFoxHub's YouTube search endpoint.
- `get_video.py` calls RedFoxHub's YouTube detail endpoint when enabled for the account.
- `comments.py` calls RedFoxHub's YouTube comment-list endpoint when enabled for the account.
- `download_video.py` calls RedFoxHub's short-video parser and optionally saves the first detected video URL when `--output-dir` is provided.
- `transcript.py` submits and polls RedFoxHub transcript extraction.

Outputs are JSON. If an endpoint is not enabled in RedFoxHub, report that exact error instead of falling back to `yt-dlp` or cookies.

## Failure Handling

If RedFoxHub returns auth, quota, unsupported endpoint, unavailable transcript, private/deleted/region-blocked video, or rate-limit errors, report the status. Do not use browser cookies, Google account tokens, or private YouTube APIs.
