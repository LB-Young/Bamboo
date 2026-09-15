---
name: gzh-reach
description: Query WeChat Official Account articles and accounts through documented RedFoxHub APIs.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - wechat
      - official-account
      - gzh
      - article
      - retrieval
      - redfoxhub
---

# GZH Reach

## When to Use

Use this skill for WeChat Official Account capabilities covered by the local RedFoxHub API documents copied into each script header: AI vertical article search, keyword article search, keyword account search, real-time article content by URL, and account article list.

Do not use this skill for undocumented Official Account APIs, browser automation, login-only data, posting, comments, private accounts, or state-changing actions.

## Authentication

All scripts require `REDFOX_API_KEY`, usually loaded from `~/.bamboo/.env`.

## Scripts

```bash
python <skill_dir>/scripts/search_ai_articles.py "人工智能" --page-num 1 --page-size 20 --start-time "2026-06-01 00:00:00" --end-time "2026-06-01 23:59:59"
python <skill_dir>/scripts/search_articles.py "人工智能" --offset 0 --sort-type 0
python <skill_dir>/scripts/search_accounts.py "十点读书" --offset 0
python <skill_dir>/scripts/get_article.py "https://mp.weixin.qq.com/s/i4pZP3kBuMnxr-1js8200w"
python <skill_dir>/scripts/list_account_articles.py --account duhaoshu --offset 0 --sort-type 2
python <skill_dir>/scripts/list_account_articles.py --wx-id gh_5c7e8b7f586b
python <skill_dir>/scripts/list_account_articles.py --biz-info "MjM5MDMyMzg2MA=="
```

Each script has the official request and response example copied at the top of the file. Keep behavior aligned with that embedded document.
