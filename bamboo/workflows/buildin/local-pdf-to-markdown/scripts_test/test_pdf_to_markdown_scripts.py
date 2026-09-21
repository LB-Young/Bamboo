"""Offline tests for the local PDF workflow scripts."""

from __future__ import annotations

import os
import py_compile
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
PYTHON_SCRIPT = SCRIPTS_DIR / "pdf_to_markdown.py"
SHELL_SCRIPT = SCRIPTS_DIR / "run.sh"


def test_python_script_compiles_and_exposes_help(tmp_path: Path) -> None:
    py_compile.compile(str(PYTHON_SCRIPT), cfile=str(tmp_path / "pdf_to_markdown.pyc"), doraise=True)
    result = subprocess.run([sys.executable, str(PYTHON_SCRIPT), "--help"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_shell_wrapper_has_valid_syntax(tmp_path: Path) -> None:
    source = SHELL_SCRIPT.read_text(encoding="utf-8")
    assert source.startswith("#!/usr/bin/env bash\n")
    bash = shutil.which("bash")
    if bash is None or (os.name == "nt" and "system32" in bash.lower()):
        pytest.skip("a directly usable bash is not installed on this platform")
    local_script = tmp_path / SHELL_SCRIPT.name
    shutil.copy2(SHELL_SCRIPT, local_script)
    result = subprocess.run([bash, "-n", local_script.name], cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_auto_device_prefers_cuda(monkeypatch) -> None:
    fake_cuda = SimpleNamespace(device_count=lambda: 2)
    fake_device = SimpleNamespace(is_compiled_with_cuda=lambda: True, cuda=fake_cuda)
    monkeypatch.setitem(sys.modules, "paddle", SimpleNamespace(device=fake_device))
    namespace = runpy.run_path(str(PYTHON_SCRIPT))
    assert namespace["resolve_paddle_device"]("auto") == "gpu:0"
    assert namespace["resolve_paddle_device"]("cpu") == "cpu"
