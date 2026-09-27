---
name: paper-reach
description: Download papers and technical reports robustly from arXiv, Hugging Face, GitHub release assets, and direct PDF URLs, with resumable downloads and optional VPN proxy configuration.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - paper
      - arxiv
      - pdf
      - download
      - research
---

# Paper Reach

## When to Use

Use this skill when the user asks to download, mirror, complete, or verify papers, technical reports, model cards, or research PDFs.

This skill is designed for long paper-download sessions where files may be large or network connectivity may be unstable. It avoids short global timeouts, supports resumable downloads, and validates that the saved file looks like a PDF.

## VPN / Proxy

If a VPN or local proxy is needed, set `VPN_PROT` in `.env`:

```dotenv
VPN_PROT=http://127.0.0.1:<port>
```

The script reads `VPN_PROT` only from `.env` files in the current working directory or `~/.bamboo/.env`. It does not probe, guess, or hard-code proxy ports. Values such as `<port>` and `127.0.0.1:<port>` are normalized to `http://127.0.0.1:<port>`.

## Commands

Download one PDF URL:

```bash
python <skill_dir>/scripts/paper_cli.py download "https://arxiv.org/pdf/2407.21783" --output "/path/to/Llama-3.pdf"
```

Download an arXiv paper by id:

```bash
python <skill_dir>/scripts/paper_cli.py arxiv 2407.21783 --output-dir "/path/to/技术报告" --series meta --filename "Llama-3.pdf"
```

Download a manifest:

```bash
python <skill_dir>/scripts/paper_cli.py manifest papers.yaml --output-dir "/path/to/技术报告"
```

Manifest items may be a JSON/YAML list or a mapping with a `papers` list:

```yaml
papers:
  - series: meta
    filename: Llama-3.pdf
    url: https://arxiv.org/pdf/2407.21783
    expected_bytes: 9833173
  - path: qwen/Qwen-VL.pdf
    arxiv_id: "2308.12966"
```

Inspect an existing manifest without downloading:

```bash
python <skill_dir>/scripts/paper_cli.py status papers.yaml --output-dir "/path/to/技术报告"
```

Normalize an arXiv id or URL:

```bash
python <skill_dir>/scripts/paper_cli.py normalize 2407.21783
```

## Workflow

1. Load this skill before planning a bulk paper download.
2. Prefer a manifest for multi-paper work. Include `series`, `filename`, `url` or `arxiv_id`, and `expected_bytes` when known.
3. Download into a staging directory first; the script writes partial files there and only replaces the final output after validation.
4. Use `--retries` and the default resumable behavior for unstable connections.
5. Keep already downloaded complete files; do not redownload unless the user asks for `--overwrite`.
6. Summarize completed, skipped, failed, and incomplete papers separately.

## Failure Handling

- If `VPN_PROT` is malformed, fix the `.env` value before retrying.
- If a server does not support `Range`, the script restarts the staging file cleanly.
- If the final file is smaller than `expected_bytes` or does not start with `%PDF`, treat it as incomplete or invalid and do not copy it over a good existing file.
- Do not use `curl | bash`, downloaded scripts, browser cookies, or private credentials for paper downloads.
