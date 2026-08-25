---
name: socratic-questioning
description: Clarify a vague or tangled question through one-at-a-time Socratic questioning before giving advice.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - clarification
      - reasoning
      - chinese
---

# Socratic Questioning

## Source

Adapted for Bamboo from xiaolouJB/prompt-toolkit, prompt 01 "苏格拉底式提问（Socratic Questioning）".

Original project: https://github.com/xiaolouJB/prompt-toolkit

The upstream repository attributes the prompt collection to 数字生命卡兹克 and distributes the adapted collection under CC BY-NC 4.0. Keep attribution and do not use this built-in skill for commercial redistribution without checking the upstream/source license.

## When to Use

Use this skill when the user's request is under-specified, self-contradictory, emotionally loaded, or likely to produce the wrong work if answered immediately.

Typical triggers:

- 用户说“用苏格拉底式提问”“帮我想清楚”“我不知道该怎么问”。
- The user describes confusion, a broad problem, or a decision but has not pinned down the actual question.
- Important terms, constraints, evidence, or success criteria are unclear.

Do not use this skill when the user gave a concrete executable task and the next step is obvious.

## Workflow

1. Do not give advice first.
2. State in one sentence what you currently understand about the user's confusion.
3. Ask exactly one question at a time.
4. Use no more than six total questions unless the user explicitly asks to continue.
5. Prioritize questions that separate:
   - Verifiable facts.
   - Interpretations of those facts.
   - Value judgments.
   - Desired outcomes.
   - Assumptions and missing evidence.
6. Before each follow-up question, briefly say what the previous answer changed in your understanding.
7. Stop as soon as the real question is clear. Do not ask filler questions to reach six.

## Completion Output

When the questioning phase is complete, summarize:

- Initial question.
- Real question.
- Confirmed facts.
- Unverified assumptions.
- Key variable that could change the conclusion.
- A clearer, actionable question the user can confirm.

After the user confirms the clarified question, answer it directly with judgment, reasons, and next action.

## Guardrails

- Keep each question short and decision-relevant.
- Avoid turning the interaction into a survey.
- If the user asks to stop clarifying and proceed, proceed with explicit assumptions.
