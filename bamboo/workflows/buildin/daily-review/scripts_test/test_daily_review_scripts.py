"""Offline tests for the daily-review workflow scripts."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCRIPT = SCRIPTS_DIR / "project_snapshot.sh"


def test_project_snapshot_has_strict_shell_header() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in source


def test_project_snapshot_passes_bash_syntax_check(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not installed on this platform")
    if os.name == "nt" and "system32" in bash.lower():
        pytest.skip("WSL bash launcher is not a directly usable test shell")
    local_script = tmp_path / SCRIPT.name
    shutil.copy2(SCRIPT, local_script)
    result = subprocess.run([bash, "-n", local_script.name], cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
