---
name: humanize-writing
description: Edit prose so it reads less like AI-generated text while preserving facts, claims, structure that matters, and the intended reader outcome.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - writing
      - editing
      - humanize
      - anti-ai-tone
      - article
---

# Humanize Writing

## When to Use

Use this skill after a draft exists and the task needs a final prose pass before publishing, especially for public articles, product copy, social posts, README prose, newsletters, and WeChat public-account drafts.

Use it when the draft feels too much like a model answer: generic, over-polished, promotional, mechanical, repetitive, full of staged contrasts, or padded with transitions that do not add facts.

Do not use it to change the factual position of the article, add unsupported color, imitate a named living writer, or hide authorship metadata. This is an editorial quality pass, not deception or fact invention.

## Core Rule

Preserve the information, not the exact shape. Every factual claim, number, name, date, source, quote, limitation, and technical distinction must survive unless the caller explicitly asks to cut it. You may reorder, compress, split, merge, or rewrite paragraphs when that makes the article read like authored prose.

Never invent facts. If the draft needs a concrete detail to avoid vague AI-sounding prose, use only details already present in the source material or verified external notes. Otherwise, write the plain version and mark the missing detail for follow-up.

## Edit Targets

Check every reader-visible string, not only body paragraphs:

- title and subtitle;
- section headings;
- captions and table labels;
- pull quotes and callouts;
- list labels and lead-ins;
- conclusion and final takeaway.

## AI-Smell Patterns To Remove

- Staged contrast: "not only X, but Y", "this is not just..., it is...".
- Generic run-up: "in today's rapidly changing landscape", "let's dive in", "at its core".
- Inflated significance without evidence: "pivotal", "revolutionary", "game-changing", "marks a new era".
- Mechanical triads: three examples or adjectives where two or four would be more natural.
- Decorative emphasis: unnecessary bolding, slogan-like one-line closers, repeated rhetorical questions.
- Loose catalogs: long lists that avoid choosing what matters.
- Vague authority: "experts say", "research shows", "it is widely believed" without a named source.
- Passive or missing actors when an actor is known and useful.
- Repeated paragraph shape: context sentence, contrast sentence, "what matters is..." ending.
- Polished filler: "seamlessly", "robust", "leverage", "unlock", "delve", "showcase", "underscore", unless the word is the exact technical term.

## Workflow

1. Read the whole draft and source notes before editing.
2. Identify the intended reader, the article's central claim, and the few details that must not be lost.
3. Make an internal pattern audit using the list above.
4. Rewrite in embedded mode by default: output only the improved text when another workflow is calling this skill.
5. Keep technical terms, code identifiers, equations, links, citations, and asset paths unchanged unless they are visibly wrong.
6. Prefer concrete verbs and short transitions. Let some paragraphs simply state the point.
7. Vary sentence length and paragraph length naturally; do not force every section into the same template.
8. Re-check against the source draft and restore any lost nuance, caveat, number, or source boundary.
9. If the draft needs missing background, newer evidence, or a verified link to sound grounded, stop and request/search for that information before finalizing.

## WeChat Article House Style

For WeChat technical pushes:

- Use a title that names the real topic, not a slogan.
- Open with the concrete problem or why the reader should care; avoid "recently, X has attracted widespread attention" unless the source proves it.
- Put background before it blocks understanding, but do not turn every article into a literature review.
- Captions should explain what the image/table proves or clarifies.
- The ending should leave the reader with one or two grounded takeaways, not a grand summary.

## Output Modes

- Embedded mode: return only the revised article text or revised section. Use this inside workflows.
- Review mode: return concise findings with quoted examples and suggested fixes when the caller asks whether a draft has AI flavor.
- File mode: when given a local file path, rewrite reader-visible prose in place and report a short summary. Preserve code blocks, data blocks, frontmatter, URLs, and image paths.

## Attribution

This Bamboo skill is a local, condensed adaptation inspired by open-source humanizing-writing skills and public AI-writing-pattern guidance. It is not a verbatim copy; keep future updates concise and workflow-oriented.
