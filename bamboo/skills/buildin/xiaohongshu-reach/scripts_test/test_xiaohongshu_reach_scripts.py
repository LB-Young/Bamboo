"""Offline smoke tests for the executable scripts shipped by this skill."""

from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCRIPTS = sorted(SCRIPTS_DIR.glob("*.py"))


def test_skill_contains_executable_scripts() -> None:
    assert SCRIPTS, f"no Python scripts found in {SCRIPTS_DIR}"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_script_compiles_and_exposes_help(script: Path, tmp_path: Path) -> None:
    py_compile.compile(str(script), cfile=str(tmp_path / f"{script.stem}.pyc"), doraise=True)
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
