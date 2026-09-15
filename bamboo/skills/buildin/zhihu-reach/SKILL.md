---
name: zhihu-reach
description: Query Zhihu hotspot rankings and keyword hotspot matches through RedFoxHub APIs.
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

Use this skill when the task needs Zhihu hot-rank data, Zhihu keyword hotspot history, RedFoxHub aggregated top hotspot events, or Zvideo download parsing.

RedFoxHub's public SDK/API surface currently exposes Zhihu through the hotspot interfaces, not direct question, answer, article, or profile detail APIs. Do not use this skill when the user needs full Zhihu page text or logged-in answer/comment extraction unless a separate RedFoxHub Zhihu detail endpoint is added.

## Authentication

All scripts call RedFoxHub and require `REDFOX_API_KEY`.

```bash
export REDFOX_API_KEY="ak_xxxx"
```

The optional `REDFOX_BASE_URL` overrides the default host `https://redfox.hk`.

## Scripts

```bash
python <skill_dir>/scripts/hot_rank.py 2026-09-13 2026-09-14
python <skill_dir>/scripts/search_hotspots.py "AI,机器人" 2026-09-01 2026-09-14
python <skill_dir>/scripts/top10.py "2026-09-13 00:00:00" "2026-09-14 00:00:00"
python <skill_dir>/scripts/download_video.py "https://www.zhihu.com/zvideo/..."
python <skill_dir>/scripts/download_video.py "https://www.zhihu.com/zvideo/..." --output-dir ./downloads
```

## Capability Notes

- `hot_rank.py` calls RedFoxHub hotspot platform rank with platform code `9` for Zhihu.
- `search_hotspots.py` searches hotspot history for one or more keywords restricted to Zhihu.
- `top10.py` fetches RedFoxHub's all-platform aggregated top 10 hotspot events, useful when the user wants context beyond Zhihu.
- `download_video.py` calls RedFoxHub's short-video parser and optionally saves the first detected video URL when `--output-dir` is provided.

Outputs are JSON. Treat hotspot scripts as hotspot/rank data, not full Zhihu article or answer bodies.

## Failure Handling

If RedFoxHub returns auth, quota, unsupported endpoint, or rate-limit errors, report that status. Do not fall back to direct Zhihu crawling, browser-cookie extraction, or private APIs.
