---
name: vertical-horizontal-analysis
description: Research a topic through vertical history and horizontal comparison, keeping facts, inferences, and opinions separate.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - research
      - analysis
      - comparison
      - chinese
---

# Vertical Horizontal Analysis

## Source

Adapted for Bamboo from xiaolouJB/prompt-toolkit, prompt 04 "横纵分析法（Horizontal-Vertical Analysis）".

Original project: https://github.com/xiaolouJB/prompt-toolkit

The upstream repository attributes the prompt collection to 数字生命卡兹克 and distributes the adapted collection under CC BY-NC 4.0. Keep attribution and do not use this built-in skill for commercial redistribution without checking the upstream/source license.

## When to Use

Use this skill for deep research on a product, company, technology, person, industry, event, or project where both historical development and peer comparison matter.

Typical triggers:

- 用户说“横纵分析”“深度研究一下”“纵向脉络和横向对比”。
- The user needs traceable conclusions, a timeline, comparison dimensions, and future paths.

Do not use this skill for quick explanations or answers that do not need evidence.

## Workflow

1. Define the research object, scope, cutoff date, and intended use.
2. Gather evidence from the best available sources. Prefer primary sources such as official documents, raw data, papers, filings, interviews, release notes, and direct code inspection.
3. Vertical analysis:
   - Origin context and need.
   - Key actors or drivers.
   - Major turns, successes, and failures.
   - Early choices that became strengths, dependencies, or burdens.
4. Horizontal analysis:
   - Choose comparison objects and explain why.
   - Compare with shared dimensions.
   - Explain why users, customers, maintainers, or markets choose or reject each option.
5. Synthesize the two axes:
   - How past capabilities and constraints affect the future.
   - Three plausible future paths.
   - Preconditions and warning signals for each path.
6. Separate facts, inferences, and opinions.
7. Mark unverified claims explicitly.

## Output Shape

- Core conclusion.
- Scope and evidence cutoff.
- Key timeline.
- Horizontal comparison table.
- Detailed analysis.
- Future paths.
- Open questions.
- Source notes with dates where available.

## Guardrails

- For current topics, browse or inspect fresh primary sources before making factual claims.
- Present conflicting evidence side by side.
- Do not pad the report; depth should come from evidence and comparisons.
