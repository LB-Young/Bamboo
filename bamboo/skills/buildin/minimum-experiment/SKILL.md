---
name: minimum-experiment
description: Replace speculation with a low-cost, reversible experiment that tests the assumption most likely to change a decision.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - decision-making
      - validation
      - experimentation
      - chinese
---

# Minimum Experiment

## Source

Adapted for Bamboo from xiaolouJB/prompt-toolkit, prompt 10 "用最小实验替代空想（Minimum Experiment）".

Original project: https://github.com/xiaolouJB/prompt-toolkit

The upstream repository attributes the prompt collection to 数字生命卡兹克 and distributes the adapted collection under CC BY-NC 4.0. Keep attribution and do not use this built-in skill for commercial redistribution without checking the upstream/source license.

## When to Use

Use this skill when a user is stuck debating a plan, product idea, architecture choice, workflow change, or personal decision that can be tested cheaply.

Typical triggers:

- 用户说“用最小实验”“先验证一下”“别空想”。
- The decision depends on assumptions that can be observed within days.
- The cost of a full implementation is high compared with a small reversible test.

Do not use this skill when the decision is irreversible and unsafe to test without expert review.

## Workflow

1. Restate the decision or idea being debated.
2. List the three assumptions that most affect the outcome.
3. Pick the one assumption most likely to change the final conclusion.
4. Design the smallest experiment that tests that assumption.
5. Keep the experiment low-cost, reversible, and time-boxed.
6. Define:
   - What exactly to do.
   - Time and resources required.
   - Metric or observation to collect.
   - Result that supports continuing.
   - Result that suggests stopping or changing direction.
   - New information expected at the end.
7. End with the first action that can start tomorrow or immediately.

## Output Shape

- Decision under test.
- Critical assumptions.
- Assumption selected.
- Experiment design.
- Cost and reversibility.
- Metrics.
- Continue condition.
- Stop/change condition.
- First action.

## Guardrails

- Prefer real feedback over opinion scoring.
- Avoid experiments whose result cannot change the decision.
- If the experiment touches users, money, safety, privacy, or production systems, call out approvals and blast radius.
