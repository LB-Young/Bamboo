---
name: writing-plans
description: Produce implementation plans for multi-step code changes, including phases, files touched, risks, and validation.
user-invocable: true
load-experiences: true
metadata:
  bamboo:
    tags:
      - planning
      - software-development
      - design
---

# Writing Plans

## When to Use

Use this skill before broad implementation work that touches multiple modules, introduces a new subsystem, or changes runtime behavior.

Do not use this skill for tiny single-file fixes unless the user explicitly asks for a plan.

## Plan Structure

1. Goal and non-goals.
2. Current architecture observations.
3. Proposed phases.
4. For each phase:
   - Existing files to change.
   - New files or directories to add.
   - Runtime behavior affected.
   - Tests to add or update.
   - Risks and rollback notes.
5. Explicit boundary decisions to avoid duplicate capabilities.

## Quality Bar

Plans should be concrete enough that implementation can start without rediscovering the architecture. Avoid vague items such as "improve tool system" without naming files and behavior.
