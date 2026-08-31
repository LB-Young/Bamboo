---
name: paper-reach
description: Search and inspect public research paper metadata from arXiv and DOI/Crossref without requiring paid database access.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - paper
      - arxiv
      - doi
      - research
      - retrieval
---

# Paper Reach

## When to Use

Use this skill when the task needs public research paper metadata, arXiv records, DOI records, abstracts, authors, publication dates, venue names, or paper URLs.

Do not use this skill for general web search, GitHub project research, or private academic database access.

## Privacy Boundary

Use public arXiv and Crossref metadata only. Do not attempt to access paid journals, institutional logins, private libraries, browser cookies, or account-only PDFs.

## Commands

```bash
python <skill_dir>/scripts/paper_cli.py arxiv-search "query" --max-results 5
python <skill_dir>/scripts/paper_cli.py arxiv-id 2401.00001
python <skill_dir>/scripts/paper_cli.py doi 10.1145/3368089.3409742
```

Use the same `python` environment that runs Bamboo.

## Workflow

1. Load this skill for paper-specific metadata requests.
2. Use `arxiv-search` for topic/title/author discovery on arXiv.
3. Use `arxiv-id` for a known arXiv identifier.
4. Use `doi` for a known DOI and Crossref metadata.
5. Ground final answers in returned URLs, identifiers, authors, dates, and abstracts.

## Failure Handling

If a provider returns no record, network failure, or incomplete metadata, report that limitation and suggest another identifier, DOI, title, or author query.
