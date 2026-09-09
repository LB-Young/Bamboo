#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${PYTHON:-python}" "$SCRIPT_DIR/pdf_to_markdown.py" "$@"
