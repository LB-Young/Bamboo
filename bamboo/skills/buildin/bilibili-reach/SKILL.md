---
name: bilibili-reach
description: Query and download Bilibili content through documented RedFoxHub APIs.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - bilibili
      - video
      - retrieval
      - redfoxhub
---

# Bilibili Reach

## When to Use

Use this skill for Bilibili capabilities covered by the local RedFoxHub API documents in `docs/`: video download, keyword video search, keyword account search, video detail, and account video list.

Do not use this skill for undocumented Bilibili APIs, browser automation, login-only data, comments, danmaku, favorites, or state-changing actions.

## Authentication

All scripts require `REDFOX_API_KEY`, usually loaded from `~/.bamboo/.env`.

## Scripts

```bash
python <skill_dir>/scripts/download_video.py "https://www.bilibili.com/video/BV1AmSSBMEqo/"
python <skill_dir>/scripts/search_videos.py "羽绒服" --page 1 --page-size 10 --order time
python <skill_dir>/scripts/search_accounts.py "影视飓风" --page 1 --page-size 10 --order follower
python <skill_dir>/scripts/get_video.py --bv-id BV1ghJg6hEWV
python <skill_dir>/scripts/get_video.py --work-url "https://www.bilibili.com/video/BV1ghJg6hEWV/"
python <skill_dir>/scripts/list_account_videos.py --mid 946974 --page 1 --page-size 10 --order time
python <skill_dir>/scripts/list_account_videos.py --account-url "https://space.bilibili.com/946974"
```

Each script has the official request and response example copied at the top of the file. Keep behavior aligned with the corresponding document in `docs/`.
