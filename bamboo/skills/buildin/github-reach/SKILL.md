---
name: github-reach
description: Inspect public GitHub repositories, releases, issues, pull requests, and user/org metadata through public GitHub APIs without using credentials by default.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - github
      - repository
      - open-source
      - retrieval
---

# GitHub Reach

## When to Use

Use this skill when the task needs public GitHub repository metadata, README links, releases, issues, pull requests, stars, forks, language, license, or recent activity.

Do not use this skill for preparing local commits or pull requests in the current repository; use `github-pr-workflow` for that workflow.

## Privacy Boundary

Use public GitHub API responses by default. Do not read local git credentials, browser cookies, `gh` auth state, private tokens, or private repositories unless the user explicitly provides credentials through an approved mechanism.

## Commands

```bash
python3 <skill_dir>/scripts/github_cli.py repo owner/name
python3 <skill_dir>/scripts/github_cli.py parse "https://github.com/owner/name"
python3 <skill_dir>/scripts/github_cli.py releases owner/name --max-results 5
python3 <skill_dir>/scripts/github_cli.py issues owner/name --state open --max-results 10
python3 <skill_dir>/scripts/github_cli.py prs owner/name --state open --max-results 10
python3 <skill_dir>/scripts/github_cli.py user owner
```

Use `python` instead of `python3` only when `python3` is unavailable and `python --version` reports Python 3.

## Workflow

1. Load this skill for GitHub project research and public repo inspection.
2. Use `parse` when the user pasted a GitHub URL and you only need the normalized repository name.
3. Use `repo` first for repository overview.
4. Use `releases` for recent versions and changelog links.
5. Use `issues` or `prs` for public tracker state and recent activity.
6. Ground final answers in returned URLs, dates, counts, and API fields.

## Failure Handling

If GitHub returns rate limits, not found, or access denied, report the status. Do not attempt to bypass rate limits or discover private data.
