---
name: xiaohongshu-reach
description: Query and download Xiaohongshu content through documented RedFoxHub APIs.
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

Use this skill for Xiaohongshu capabilities covered by the local RedFoxHub API documents in `docs/`: video download, note search, account search, note detail, account detail, account note list, and AI vertical note search.

Do not use this skill for undocumented Xiaohongshu APIs, browser automation, comments, hot lists, private notes, collections, publishing, or state-changing actions.

## Authentication

All scripts require `REDFOX_API_KEY`, usually loaded from `~/.bamboo/.env`.

## Scripts

```bash
python <skill_dir>/scripts/download_video.py "https://www.xiaohongshu.com/explore/..."
python <skill_dir>/scripts/search_notes.py "美食" --offset 0 --sort-type _0
python <skill_dir>/scripts/search_accounts.py "赵露思" --offset 0 --sort-type _0
python <skill_dir>/scripts/get_note.py --work-id 6a03be1b0000000035033163
python <skill_dir>/scripts/get_note.py --work-link "https://www.xiaohongshu.com/explore/..."
python <skill_dir>/scripts/get_account.py rosy1109 --user-id 5a73c5fa4eacab4c4ccc9778
python <skill_dir>/scripts/list_account_notes.py --red-id rosy1109 --offset 0
python <skill_dir>/scripts/search_ai_notes.py AI --start-time "2026-06-01 00:00:00" --end-time "2026-06-02 00:00:00"
```

Each script has the official request and response example copied at the top of the file. Keep behavior aligned with the corresponding document in `docs/`.
