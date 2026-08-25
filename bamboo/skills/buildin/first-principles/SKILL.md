---
name: first-principles
description: Break a problem down to confirmed facts, goals, assumptions, resources, and constraints, then rebuild a solution from first principles.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - problem-solving
      - reasoning
      - architecture
      - chinese
---

# First Principles

## Source

Adapted for Bamboo from xiaolouJB/prompt-toolkit, prompt 07 "第一性原理（First Principles）".

Original project: https://github.com/xiaolouJB/prompt-toolkit

The upstream repository attributes the prompt collection to 数字生命卡兹克 and distributes the adapted collection under CC BY-NC 4.0. Keep attribution and do not use this built-in skill for commercial redistribution without checking the upstream/source license.

## When to Use

Use this skill when a problem is being handled by habit, local patches, cargo-cult architecture, or inherited assumptions.

Typical triggers:

- 用户说“用第一性原理”“推倒重来想一下”“别按惯例想”。
- Existing solutions feel overfit, fragile, expensive, or conceptually confused.
- A technical design or product decision needs to be rebuilt from fundamental constraints.

Do not use this skill for routine debugging where a narrow reproduction and fix is enough.

## Workflow

1. Name the problem and the outcome the user actually wants.
2. Separate the situation into:
   - Confirmed facts that cannot be ignored.
   - Assumptions that are accepted by habit but not verified.
   - The real objective.
   - Available resources.
   - Hard constraints.
3. Temporarily set aside industry conventions, existing implementation details, and the current proposed solution.
4. Re-derive possible paths from facts, goals, and constraints.
5. Compare the current/default path against the derived path.
6. Identify where the original plan is only patching symptoms.
7. Propose the smallest first validation step.

## Output Shape

- Problem: concise restatement.
- Basic facts: what is known.
- Suspect assumptions: what needs verification.
- Real goal and constraints.
- Surface patches: parts of the current plan that do not address the core.
- Re-derived path: solution rebuilt from basics.
- Preconditions: what must be true for this path to work.
- First validation step.

## Guardrails

- Do not use "first principles" as a slogan for speculative reinvention.
- Preserve existing working constraints unless there is evidence they are accidental.
- In code tasks, inspect the relevant code before claiming which assumptions are real.
