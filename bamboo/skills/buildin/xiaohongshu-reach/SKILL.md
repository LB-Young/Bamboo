---
name: xiaohongshu-reach
description: Inspect public Xiaohongshu note URLs or shared text and extract publicly visible metadata without reading cookies by default.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - xiaohongshu
      - rednote
      - social
      - retrieval
---

# Xiaohongshu Reach

## When to Use

Use this skill when the task needs Xiaohongshu/RedNote public note links, note ids, share text parsing, or publicly visible page metadata.

Do not use this skill for Bilibili, YouTube, RSS, or generic web search tasks.

## Privacy Boundary

Use public URLs and public HTML only. Do not read browser cookies, local app storage, QR-login state, account tokens, or private API credentials. If Xiaohongshu returns login walls, risk-control pages, CAPTCHA, or incomplete public HTML, explain the block instead of trying account access.

## Commands

The bundled helper supports public URL and share-text workflows:

```bash
python3 <skill_dir>/scripts/xiaohongshu_cli.py parse "share text or Xiaohongshu URL"
python3 <skill_dir>/scripts/xiaohongshu_cli.py note "https://www.xiaohongshu.com/explore/..."
python3 <skill_dir>/scripts/xiaohongshu_cli.py search-url "keyword"
```

Use `python` instead of `python3` only when `python3` is unavailable and `python --version` reports Python 3.

## Workflow

1. Load this skill for Xiaohongshu-specific requests.
2. Use `parse` first when the user pasted Xiaohongshu share text; return extracted URLs, note ids, and canonical links.
3. Use `note` for a known public note URL to fetch and summarize public page metadata such as title, description, canonical URL, OpenGraph fields, and detected note id.
4. Use `search-url` when the user needs a Xiaohongshu search link for a keyword and public search fetching is not required.
5. Keep final answers grounded in returned public URLs and command output.
6. Do not claim access to comments, private notes, personalized feeds, logged-in search results, or full note content unless the command result explicitly contains it.

## Failure Handling

If public pages fail, redirect to a login wall, or return risk-control content, report the status and ask for a public note URL or pasted public content. Do not bypass rate limits, CAPTCHA, or login requirements.
