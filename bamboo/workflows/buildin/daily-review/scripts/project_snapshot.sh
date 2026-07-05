#!/usr/bin/env bash
set -euo pipefail

focus="${1:-}"
printf 'focus: %s\n' "$focus"
printf 'cwd: %s\n' "$(pwd)"
printf 'top-level files:\n'
find . -maxdepth 1 -mindepth 1 -print | sort | head -40
