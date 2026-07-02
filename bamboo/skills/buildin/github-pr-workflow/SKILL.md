---
name: github-pr-workflow
description: Prepare GitHub pull request work using existing git and gh commands while respecting Bamboo permission and audit rules.
user-invocable: true
load-experiences: true
metadata:
  bamboo:
    tags:
      - github
      - pull-request
      - git
---

# GitHub PR Workflow

## When to Use

Use this skill when preparing, checking, summarizing, or updating a GitHub pull request.

## Workflow

1. Inspect the current branch and working tree before making changes.
2. Review the diff and relevant tests.
3. Draft a concise PR title and description from actual changes.
4. Prefer `gh` CLI when available for PR metadata; do not print tokens or secrets.
5. Use `bash` for git and gh commands. Read-only commands such as `git status`, `git diff`, and `git log` are safe by default. Network or write operations require permission unless the run is configured with `--yes` or bypass mode.
6. Never force-push or rewrite git history unless the user explicitly asks and the runtime policy allows it.

## PR Description Shape

- Summary.
- Tests.
- Risks or follow-up notes.

Avoid inventing issue numbers, reviewers, or CI status.
