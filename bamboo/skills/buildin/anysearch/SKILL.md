---
name: anysearch
description: Search the live web, run small parallel searches, and extract Markdown content from URLs through the AnySearch API.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - search
      - web
      - retrieval
---

# AnySearch

## When to Use

Use this skill when the task needs current external information, fact checking, web search, domain-specific search, or full-page URL extraction.

Do not use this skill for local repository search. Use Bamboo file tools such as `grep`, `glob`, and `read` for local files.

## Privacy Boundary

AnySearch sends search queries, extracted URLs, and optional API keys to `https://api.anysearch.com/mcp`. Do not send passwords, private user data, unreleased business information, or project secrets unless the user explicitly accepts that external disclosure.

An API key is optional. Anonymous access may work with lower rate limits. If the user configures a key, prefer `ANYSEARCH_API_KEY` in the environment or in this skill directory's `.env` file.

## Commands

The bundled Bamboo integration is intentionally minimal:

```bash
python3 <skill_dir>/scripts/anysearch_cli.py search "query" --max-results 5
python3 <skill_dir>/scripts/anysearch_cli.py batch-search --query "q1" --query "q2" --max-results 3
python3 <skill_dir>/scripts/anysearch_cli.py extract "https://example.com/page"
python3 <skill_dir>/scripts/anysearch_cli.py get-sub-domains --domain finance
```

Use `python` instead of `python3` only when `python3` is unavailable and `python --version` reports Python 3.

## Workflow

1. Load this skill before searching the live web.
2. Decide whether the query is a general web query or domain-specific.
3. For general searches, call `search` with a concise query and `--max-results` between 1 and 10.
4. For multiple independent queries, call `batch-search` with two to five `--query` arguments.
5. For domain-specific searches, call `get-sub-domains` first, then search with `--domain`, `--sub-domain`, and any required `--sdp` key-value parameters.
6. If snippets are insufficient, call `extract` on the most relevant result URL.
7. In the final answer, cite the URLs returned by search or extraction and distinguish sourced facts from your own inference.

## Vertical Domains

Supported domains include:

`resource`, `social_media`, `finance`, `academic`, `legal`, `health`, `business`, `security`, `ip`, `code`, `energy`, `environment`, `agriculture`, `travel`, `film`, and `gaming`.

For vertical search, `--sdp` accepts comma-separated key-value pairs:

```bash
python3 <skill_dir>/scripts/anysearch_cli.py search "AAPL" --domain finance --sub-domain finance.quote --sdp type=stock,symbol=AAPL,cn_code= --max-results 5
```

## Error Handling

If AnySearch is unavailable, rate-limited, or blocked by network policy, tell the user what failed and use another available search method only when appropriate for the task.
