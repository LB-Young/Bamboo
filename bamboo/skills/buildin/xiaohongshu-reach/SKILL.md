---
name: xiaohongshu-reach
description: Query Xiaohongshu notes, accounts, account notes, hot-note lists, and comments through RedFoxHub APIs.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - xiaohongshu
      - rednote
      - social
      - retrieval
      - redfoxhub
---

# Xiaohongshu Reach

## When to Use

Use this skill when the task needs Xiaohongshu note search, account search, account details, note details, account note lists, hot-note discovery, hot accounts, or comment retrieval through RedFoxHub.

Do not use this skill for direct browser automation, login-only pages, private notes, private collections, publishing, liking, following, or messaging.

## Authentication

All scripts call RedFoxHub and require `REDFOX_API_KEY`.

```bash
export REDFOX_API_KEY="ak_xxxx"
```

The optional `REDFOX_BASE_URL` overrides the default host `https://redfox.hk`.

## Scripts

```bash
python <skill_dir>/scripts/search_notes.py "旅行" --offset 0 --sort-type 2
python <skill_dir>/scripts/search_accounts.py "美妆" --offset 0
python <skill_dir>/scripts/get_note.py --work-id 6a2ac3020000000035022d8e
python <skill_dir>/scripts/get_note.py --work-link "https://www.xiaohongshu.com/explore/..."
python <skill_dir>/scripts/get_account.py "red_id_or_account_id" --user-id "optional_user_id"
python <skill_dir>/scripts/list_account_notes.py --red-id "red_id" --offset 0 --sort-type _2
python <skill_dir>/scripts/hot_notes.py --kind search --keyword "防晒" --page-num 1 --page-size 10
python <skill_dir>/scripts/hot_notes.py --kind daily --rank-date 2026-09-13 --category 综合全部
python <skill_dir>/scripts/hot_notes.py --kind weekly --category 美味佳肴
python <skill_dir>/scripts/hot_notes.py --kind dark-horse --keyword "睫毛膏" --start-date 2026-08-15
python <skill_dir>/scripts/hot_notes.py --kind hot-accounts --date-type 1 --rank-date 2026-09-13 --type 综合全部
python <skill_dir>/scripts/comments.py submit "opus_id" --data-num 100
python <skill_dir>/scripts/comments.py result "task_id_from_submit"
```

## Capability Notes

- `search_notes.py` searches notes.
- `search_accounts.py` searches creators/accounts.
- `get_note.py` fetches one note by id or link.
- `get_account.py` fetches one creator/account.
- `list_account_notes.py` lists notes from one account.
- `hot_notes.py` covers hot-note search, daily/weekly hot lists, low-follower explosive notes, and hot accounts.
- `comments.py` submits and polls comment tasks.

Outputs are JSON. State clearly when a result comes from RedFoxHub's premium library, hot-list dataset, or an async task result.

## Failure Handling

If RedFoxHub returns auth, quota, unsupported endpoint, task-not-ready, or rate-limit errors, report that status and stop. Do not bypass Xiaohongshu protections, inspect browser storage, or extract cookies.
