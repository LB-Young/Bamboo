---
name: requesting-code-review
description: Review code changes with a findings-first structure focused on correctness, regressions, security, and missing tests.
user-invocable: true
load-experiences: true
metadata:
  bamboo:
    tags:
      - code-review
      - software-development
      - quality
---

# Requesting Code Review

## When to Use

Use this skill when the user asks for a review, audit, risk assessment, or second look at code changes.

## Review Workflow

1. Inspect the changed files and relevant surrounding code.
2. Prioritize bugs, regressions, security issues, data loss, and missing tests.
3. Report findings first, ordered by severity.
4. Include file and line references where possible.
5. Keep summaries secondary. If no issues are found, say that clearly and mention residual test gaps.

## Finding Format

Each finding should include:

- Severity or priority.
- File and line.
- Concrete problem.
- Why it matters.
- Suggested fix direction.

Do not spend review space on style-only comments unless they hide a real maintainability or correctness risk.
