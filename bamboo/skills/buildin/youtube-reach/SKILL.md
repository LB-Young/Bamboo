---
name: youtube-reach
description: Download YouTube videos through the documented RedFoxHub API.
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

Use this skill only for the YouTube video download capability covered by the local RedFoxHub API document in `docs/`.

Do not use this skill for undocumented YouTube APIs, search, comments, transcripts, browser automation, Google login, playlists, uploading, or channel management.

## Authentication

The script requires `REDFOX_API_KEY`, usually loaded from `~/.bamboo/.env`.

## Scripts

```bash
python <skill_dir>/scripts/download_video.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

The script has the official request and response example copied at the top of the file. Keep behavior aligned with the corresponding document in `docs/`.
