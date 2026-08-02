---
name: zhihu-reach
description: Parse public Zhihu URLs and extract publicly visible page metadata without reading browser cookies or login state by default.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - zhihu
      - q-and-a
      - social
      - retrieval
---

# Zhihu Reach

## When to Use

Use this skill when the task needs Zhihu public question, answer, article, column, or zvideo links and publicly visible page metadata.

Do not use this skill for generic web search, Xiaohongshu, Bilibili, YouTube, or private account data.

## Privacy Boundary

Use public URLs and public HTML only. Do not read browser cookies, local storage, login state, account tokens, or private API credentials. If Zhihu returns login walls, CAPTCHA, risk-control pages, or incomplete public HTML, explain the block instead of trying account access.

## Commands

```bash
python3 <skill_dir>/scripts/zhihu_cli.py parse "Zhihu share text or URL"
python3 <skill_dir>/scripts/zhihu_cli.py page "https://www.zhihu.com/question/..."
python3 <skill_dir>/scripts/zhihu_cli.py search-url "keyword"
```

Use `python` instead of `python3` only when `python3` is unavailable and `python --version` reports Python 3.

## Workflow

1. Load this skill for Zhihu-specific requests.
2. Use `parse` first when the user pasted Zhihu share text; return extracted URLs and detected entities.
3. Use `page` for a known public Zhihu URL to fetch and summarize public page metadata.
4. Use `search-url` when the user needs a Zhihu search link for a keyword and public search fetching is not required.
5. Keep final answers grounded in returned public URLs and command output.
6. Do not claim access to comments, logged-in answers, private drafts, follower-only content, or personalized feeds unless the command result explicitly contains it.

## Failure Handling

If public pages fail, redirect to a login wall, or return risk-control content, report the status and ask for a public URL or pasted public content. Do not bypass rate limits, CAPTCHA, or login requirements.
