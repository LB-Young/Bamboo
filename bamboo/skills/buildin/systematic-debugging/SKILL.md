---
name: systematic-debugging
description: Systematically diagnose software failures by reproducing, isolating, explaining, and verifying the root cause before changing code.
user-invocable: true
load-experiences: true
metadata:
  bamboo:
    tags:
      - debugging
      - software-development
      - verification
---

# Systematic Debugging

## When to Use

Use this skill when a bug, failing test, traceback, regression, flaky behavior, or unexpected runtime output needs investigation.

Do not use this skill for broad feature planning unless there is a concrete failure to explain.

## Workflow

1. Restate the observed failure in concrete terms.
2. Reproduce the failure with the smallest available command, test, or input.
3. Inspect the code path using `read`, `grep`, and `glob` before editing.
4. Form one or two explicit hypotheses and identify the evidence that would confirm or reject each one.
5. Run targeted read-only or test commands through `bash` when useful. Commands that write, install packages, access network, or mutate git state require permission.
6. Make the smallest code change that addresses the root cause.
7. Re-run the reproduction command and any nearby regression tests.
8. Summarize the root cause, changed files, and verification result.

## Output Expectations

Keep the final answer focused on:

- Root cause.
- Fix made.
- Tests or commands run.
- Remaining risk if full verification was not possible.
