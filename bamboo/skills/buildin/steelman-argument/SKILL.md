---
name: steelman-argument
description: Apply bidirectional steel-man reasoning to a difficult decision by constructing the strongest case for each option before asking one key clarifying question and giving a judgment.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - decision-making
      - reasoning
      - chinese
---

# Steelman Argument

## Source

Adapted for Bamboo from xiaolouJB/prompt-toolkit, prompt 09 "双向钢人论证（Steel-man Argument）".

Original project: https://github.com/xiaolouJB/prompt-toolkit

The upstream repository attributes the prompt collection to 数字生命卡兹克 and distributes the adapted collection under CC BY-NC 4.0. Keep attribution and do not use this built-in skill for commercial redistribution without checking the upstream/source license.

## When to Use

Use this skill when the user is choosing between two or more serious options and needs a fair, high-resolution decision analysis instead of quick advice.

Typical triggers:

- 用户说“用钢人论证”“双向钢人论证”“帮我做决策”“A 和 B 怎么选”。
- The decision has competing values, tradeoffs, uncertainty, or irreversible cost.
- The user may be framing the problem too narrowly and needs the choice restated first.

Do not use this skill for simple preference questions, factual lookups, or decisions where the user only wants an implementation plan.

## Workflow

1. Restate the real decision in concrete terms. Include the options, goal, constraints, time horizon, and what would count as success.
2. Build the strongest good-faith case for each option. Do not caricature either side.
3. For each option, cover:
   - Best supporting reasons.
   - Conditions where it works best.
   - Highest upside.
   - Largest downside.
   - The hardest objection that side must answer.
4. Identify the true disagreement between the options. Separate value conflicts, empirical uncertainty, risk tolerance, timing, resource constraints, and hidden assumptions.
5. Name the few variables most likely to change the conclusion.
6. Ask exactly one clarifying question if the missing information could materially change the recommendation.
7. After the user answers, give a clear judgment. Include the recommended option, why it wins under the stated constraints, when the answer would flip, and the next concrete action.

## Output Shape

When more information is needed, stop after the single clarifying question.

When enough information is available, use this structure:

- Decision: one sentence.
- Strongest case for option A.
- Strongest case for option B.
- Crux: the real deciding factor.
- Recommendation: clear choice plus reasoning.
- Flip condition: what would change the answer.
- Next action: one practical step.

## Guardrails

- Do not pretend weak evidence is decisive.
- Do not optimize only for intellectual symmetry; still make a judgment when the user asks for one.
- Surface moral, relationship, financial, legal, or safety stakes explicitly when present.
- If the decision needs current facts, laws, prices, or market data, gather or ask for that information before recommending.
