"""Unit tests for paper_cli helpers that do not touch the network."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "paper_cli.py"
SPEC = importlib.util.spec_from_file_location("paper_cli", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
paper_cli = importlib.util.module_from_spec(SPEC)
sys.modules["paper_cli"] = paper_cli
SPEC.loader.exec_module(paper_cli)


def test_normalize_arxiv_id_and_url() -> None:
    assert paper_cli.normalize_paper_url("2407.21783") == "https://arxiv.org/pdf/2407.21783"
    assert paper_cli.normalize_paper_url("https://arxiv.org/abs/2407.21783") == "https://arxiv.org/pdf/2407.21783"
    assert paper_cli.normalize_paper_url("https://arxiv.org/pdf/2407.21783") == "https://arxiv.org/pdf/2407.21783"


def test_normalized_proxy_accepts_plain_host_port() -> None:
    assert paper_cli.normalized_proxy("12345") == "http://127.0.0.1:12345"
    assert paper_cli.normalized_proxy("127.0.0.1:12345") == "http://127.0.0.1:12345"
    assert paper_cli.normalized_proxy("http://127.0.0.1:12345") == "http://127.0.0.1:12345"


def test_safe_join_rejects_path_escape(tmp_path: Path) -> None:
    with pytest.raises(paper_cli.PaperReachError):
        paper_cli.safe_join(tmp_path, "../escape.pdf")


def test_parse_env_file_reads_vpn_prot(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('VPN_PROT="http://127.0.0.1:12345"\n# comment\nBAD LINE\n', encoding="utf-8")
    assert paper_cli.parse_env_file(env)["VPN_PROT"] == "http://127.0.0.1:12345"


def test_vpn_proxy_is_read_only_from_env_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VPN_PROT", "http://127.0.0.1:54321")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert paper_cli.load_vpn_proxy_from_env_files() == ""

    (tmp_path / ".env").write_text("VPN_PROT=http://127.0.0.1:12345\n", encoding="utf-8")
    assert paper_cli.load_vpn_proxy_from_env_files() == "http://127.0.0.1:12345"


def test_pdf_validation_checks_header_and_expected_size(tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-" + (b"x" * 2048))
    assert paper_cli.pdf_is_valid(pdf, min_bytes=1024, expected_bytes=2000)
    assert not paper_cli.pdf_is_valid(pdf, min_bytes=1024, expected_bytes=100000)
