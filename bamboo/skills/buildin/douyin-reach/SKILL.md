---
name: douyin-reach
description: Query Douyin works, accounts, account works, ranks, and transcript tasks through RedFoxHub APIs.
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

Use this skill when the task needs Douyin work search, account search, account details, work details, account work lists, hot ranks, hot accounts, or RedFoxHub transcript extraction.

Do not use this skill for direct Douyin browser automation, publishing, liking, following, downloading media, or login-only creator-center data.

## Authentication

All scripts call RedFoxHub and require `REDFOX_API_KEY`.

```bash
export REDFOX_API_KEY="ak_xxxx"
```

The optional `REDFOX_BASE_URL` overrides the default host `https://redfox.hk`.

## Scripts

```bash
python <skill_dir>/scripts/search_works.py "AI" --offset 0
python <skill_dir>/scripts/search_works.py "AI" --wide --page-num 1 --page-size 10 --start-date 2026-09-01 --end-date 2026-09-14
python <skill_dir>/scripts/search_accounts.py "科技" --offset 0
python <skill_dir>/scripts/search_accounts.py "科技" --wide --page-num 1 --page-size 10
python <skill_dir>/scripts/get_work.py --work-id 7654143095876898089
python <skill_dir>/scripts/get_work.py --work-url "https://www.douyin.com/video/7654143095876898089"
python <skill_dir>/scripts/get_account.py nxpt260212
python <skill_dir>/scripts/list_account_works.py --account-id nxpt260212 --offset 0 --sort-type 2
python <skill_dir>/scripts/list_account_works.py --wide --unique-name luoyonghao --page-num 1 --page-size 10
python <skill_dir>/scripts/hot_rank.py --kind daily-hot --type 美食
python <skill_dir>/scripts/hot_rank.py --kind hot-accounts --date-type days --rank-date 2026-09-13 --type 全部
python <skill_dir>/scripts/transcript.py submit "https://www.douyin.com/video/..."
python <skill_dir>/scripts/transcript.py result "task_id_from_submit"
```

## Capability Notes

- `search_works.py` supports RedFoxHub premium and wide work-search endpoints.
- `search_accounts.py` supports premium and wide account-search endpoints.
- `get_work.py` fetches work details by id or URL.
- `get_account.py` fetches one account profile.
- `list_account_works.py` lists one account's works.
- `hot_rank.py` fetches daily hot works, daily/weekly surge ranks, or hot account recommendations.
- `transcript.py` submits and polls RedFoxHub video transcript extraction.

Outputs are JSON. For analysis, cite the returned `workUrl`, `opusUrl`, `authorLink`, or equivalent URL fields when available.

## Failure Handling

If RedFoxHub returns auth, quota, unsupported endpoint, or rate-limit errors, report that status. Do not bypass Douyin protections, inspect browser storage, extract cookies, or use private platform endpoints.
