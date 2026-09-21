"""Offline tests for the WeChat article workflow scripts."""

from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_wechat_article.py"


def test_script_compiles_and_exposes_help(tmp_path: Path) -> None:
    py_compile.compile(str(SCRIPT), cfile=str(tmp_path / "build_wechat_article.pyc"), doraise=True)
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_minimal_article_package_is_created(tmp_path: Path) -> None:
    content_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    content_dir.mkdir()
    article = tmp_path / "article.md"
    article.write_text("# 离线测试文章\n\n这是正文。\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(content_dir), str(article), str(output_dir), "--no-cover"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert list(output_dir.glob("*.docx"))
    assert (output_dir / "asset_manifest.md").is_file()
    assert (output_dir / "quality_report.md").is_file()

