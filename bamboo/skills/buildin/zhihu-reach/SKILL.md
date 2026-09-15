---
name: zhihu-reach
description: Search Zhihu works through the documented RedFoxHub API.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - zhihu
      - q-and-a
      - social
      - retrieval
      - redfoxhub
---

# Zhihu Reach

## When to Use

Use this skill only for Zhihu keyword work search covered by the local RedFoxHub API document in `docs/`.

Do not use this skill for undocumented Zhihu APIs, hot-rank APIs, top10 aggregation, browser automation, logged-in content, comments, or video download.

## Authentication

The script requires `REDFOX_API_KEY`, usually loaded from `~/.bamboo/.env`.

## Scripts

```bash
python <skill_dir>/scripts/search_works.py "未来" --offset 0 --sort upvoted_count --time-interval a_week --vertical answer
```

The script has the official request and response example copied at the top of the file. Keep behavior aligned with the corresponding document in `docs/`.
