---
name: rss-reach
description: Read RSS and Atom feeds, check recent updates, and summarize feed entries from public feed URLs.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - rss
      - atom
      - monitoring
---

# RSS Reach

## When to Use

Use this skill when the task needs to check whether a site, blog, changelog, podcast, or release feed has new entries, or when the user provides an RSS/Atom feed URL.

Do not use this skill for websites that do not expose a feed unless the task is specifically about discovering feed URLs.

## Privacy Boundary

RSS/Atom feed reads send the feed URL to the feed host. Do not include private bearer URLs, internal feed URLs, or private tokens in output unless the user explicitly provided them for this task.

## Commands

The bundled helper uses Python standard library XML parsing:

```bash
python <skill_dir>/scripts/rss_cli.py read "https://example.com/feed.xml" --max-items 20
python <skill_dir>/scripts/rss_cli.py latest "https://example.com/feed.xml"
python <skill_dir>/scripts/rss_cli.py check "https://example.com/feed.xml" --since "2026-07-01T00:00:00Z"
```

Use the same `python` environment that runs Bamboo.

## Workflow

1. Load this skill for feed update checks or feed summaries.
2. Use `read` to list recent entries with title, link, timestamp, id, and summary.
3. Use `latest` to return only the newest entry.
4. Use `check --since` when the user asks whether anything changed after a known timestamp.
5. For recurring monitoring, store the newest entry id or timestamp in Bamboo memory or cron state rather than relying on title text.
6. Cite entry links in the final answer.

## Feed Discovery

If the user gives a normal webpage, first inspect page HTML for feed links with `type="application/rss+xml"` or `type="application/atom+xml"`. Common paths are `/feed`, `/rss`, `/feed.xml`, `/atom.xml`, and `/index.xml`.
