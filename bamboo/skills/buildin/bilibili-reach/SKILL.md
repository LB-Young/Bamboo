---
name: bilibili-reach
description: Query Bilibili videos, UP accounts, account videos, and video details through RedFoxHub APIs.
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

Use this skill when the task needs Bilibili video search, UP account search, UP account details, a creator's video list, or a single video detail from RedFoxHub.

Do not use this skill for direct Bilibili browser automation, login-only data, state-changing actions, or media download.

## Authentication

All scripts call RedFoxHub and require `REDFOX_API_KEY`.

```bash
export REDFOX_API_KEY="ak_xxxx"
```

The optional `REDFOX_BASE_URL` overrides the default host `https://redfox.hk`.

## Scripts

Run scripts with the same Python environment that runs Bamboo.

```bash
python <skill_dir>/scripts/search_videos.py "AI" --page 1 --page-size 10 --order time
python <skill_dir>/scripts/search_accounts.py "影视飓风" --page 1 --page-size 10 --order follower
python <skill_dir>/scripts/get_video.py BV1ghJg6hEWV
python <skill_dir>/scripts/get_video.py "https://www.bilibili.com/video/BV1ghJg6hEWV"
python <skill_dir>/scripts/get_account.py 946974
python <skill_dir>/scripts/list_account_videos.py --mid 946974 --page 1 --page-size 10 --order time
python <skill_dir>/scripts/list_account_videos.py --account-url "https://space.bilibili.com/946974"
```

## Capability Notes

- `search_videos.py` calls RedFoxHub Bilibili video search.
- `search_accounts.py` calls RedFoxHub Bilibili UP search.
- `get_video.py` fetches one video by `bvid` or URL.
- `get_account.py` fetches one UP account by `mid`.
- `list_account_videos.py` lists videos for one UP account by `mid` or account URL.

Outputs are JSON. Keep final answers grounded in returned fields and URLs.

## Failure Handling

If RedFoxHub returns an auth, quota, unsupported endpoint, or rate-limit error, report the error and ask the user to verify `REDFOX_API_KEY`, quota, and endpoint availability. Do not fall back to Bilibili cookies, private APIs, or browser token extraction.
