---
name: test-driven-development
description: Use a focused test-first loop for implementing behavior changes with clear regression coverage.
user-invocable: true
load-experiences: true
metadata:
  bamboo:
    tags:
      - testing
      - software-development
      - implementation
---

# Test Driven Development

## When to Use

Use this skill when implementing a behavioral change, bug fix, parser rule, policy rule, or shared utility where a small regression test can clarify correctness.

Do not use this skill when the request is only documentation, exploration, or a mechanical formatting update.

## Workflow

1. Identify the behavior that should change and the smallest test surface that observes it.
2. Add or update a focused failing test first.
3. Run only the targeted test if practical.
4. Implement the minimal production change.
5. Re-run the targeted test.
6. Broaden verification only when the touched code is shared or high risk.
7. Keep unrelated refactors out of the change.

## Bamboo Tool Guidance

- Use `read`, `grep`, and `glob` to find existing test patterns.
- Use `edit` or `write` only for the files needed by the change.
- Use `bash` for test commands; write/network commands still follow PermissionPolicy.

## Final Response

Report the changed behavior and exact tests run. If no test was added, state why.
