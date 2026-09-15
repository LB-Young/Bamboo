---
name: douyin-reach
description: Query and download Douyin content through documented RedFoxHub APIs.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - douyin
      - short-video
      - creator-analysis
      - retrieval
      - redfoxhub
---

# Douyin Reach

## When to Use

Use this skill for Douyin capabilities covered by the local RedFoxHub API documents in `docs/`: video download, work search, account search, work detail, account detail, and account work list.

Do not use this skill for undocumented Douyin APIs, browser automation, publishing, comments, transcript extraction, hot ranks, or state-changing actions.

## Authentication

All scripts require `REDFOX_API_KEY`, usually loaded from `~/.bamboo/.env`.

## Scripts

```bash
python <skill_dir>/scripts/download_video.py "https://v.douyin.com/..."
python <skill_dir>/scripts/search_works.py "美食" --page-num 1 --page-size 10
python <skill_dir>/scripts/search_accounts.py "罗志祥" --page-num 1 --page-size 10
python <skill_dir>/scripts/get_work.py 7663047997038644499
python <skill_dir>/scripts/get_account.py dy_user123
python <skill_dir>/scripts/list_account_works.py --user-id 3822358551859599 --page-num 1 --page-size 10
python <skill_dir>/scripts/list_account_works.py --unique-name luoyonghao
```

Each script has the official request and response example copied at the top of the file. Keep behavior aligned with the corresponding document in `docs/`.
