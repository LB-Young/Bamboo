"""Offline tests for the video-insight workflow scripts."""

from __future__ import annotations

import py_compile
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCRIPTS = sorted(SCRIPTS_DIR.glob("*.py"))


def test_workflow_contains_executable_scripts() -> None:
    assert SCRIPTS, f"no Python scripts found in {SCRIPTS_DIR}"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_script_compiles_and_exposes_help(script: Path, tmp_path: Path) -> None:
    py_compile.compile(str(script), cfile=str(tmp_path / f"{script.stem}.pyc"), doraise=True)
    result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_output_directory_is_created_per_video(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("VIDEO_INSIGHT_OUTPUT_DIR", raising=False)
    namespace = runpy.run_path(str(SCRIPTS_DIR / "run_video_insight.py"))
    video = tmp_path / "示例 视频.mp4"
    first = namespace["resolve_output_dir"](video, None)
    assert first.parent == Path.home() / ".bamboo" / "workspace" / "video-insight"
    assert first.name == "示例_视频"


def test_video_ocr_auto_device_prefers_cuda() -> None:
    namespace = runpy.run_path(str(SCRIPTS_DIR / "analyze_keyframes.py"))
    fake_cuda = SimpleNamespace(device_count=lambda: 2)
    fake_paddle = SimpleNamespace(device=SimpleNamespace(is_compiled_with_cuda=lambda: True, cuda=fake_cuda))
    assert namespace["resolve_paddle_device"]("auto", fake_paddle) == "gpu:0"
    assert namespace["resolve_paddle_device"]("cpu", fake_paddle) == "cpu"
