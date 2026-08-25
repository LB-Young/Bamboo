---
name: reverse-engineering-example
description: Deconstruct a strong example to understand why it works, what quality choices matter, and which patterns can be reused.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - learning
      - analysis
      - product
      - software-development
      - chinese
---

# Reverse Engineering Example

## Source

Adapted for Bamboo from xiaolouJB/prompt-toolkit, prompt 03 "反向拆解（Reverse Deconstruction）".

Original project: https://github.com/xiaolouJB/prompt-toolkit

The upstream repository attributes the prompt collection to 数字生命卡兹克 and distributes the adapted collection under CC BY-NC 4.0. Keep attribution and do not use this built-in skill for commercial redistribution without checking the upstream/source license.

## When to Use

Use this skill when the user provides a strong example and wants to learn how to reproduce its quality, structure, or operating pattern.

Typical inputs:

- Product pages, interfaces, dashboards, workflows, proposals, code modules, repositories, launch plans, or written artifacts.
- 用户说“反向拆解一下”“这个为什么好”“我想学这个案例”。

Do not use this skill when the user only wants a surface summary.

## Workflow

1. Identify what problem the example solves in one sentence.
2. Identify who it serves and what success looks like.
3. Deconstruct the structure, sequence, interface, or process it uses.
4. Name the key choices that create a quality gap versus average examples.
5. Infer the completion standard implied by the example.
6. Separate reusable patterns from case-specific details.
7. Convert the findings into an actionable checklist.
8. Propose one small practice task the user can try first.

## Output Shape

- What it solves.
- Audience and goal.
- Structure or workflow.
- Quality-driving choices.
- Completion standard.
- Reusable patterns.
- Case-specific details.
- Execution checklist.
- First practice exercise.

## Guardrails

- When analyzing code, inspect files before drawing conclusions.
- Distinguish observed evidence from inferred intent.
- Avoid copying protected expression; extract transferable principles and workflows.
