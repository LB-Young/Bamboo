"""Tests for BKN ingest draft and submit."""

from __future__ import annotations

from pathlib import Path

import pytest

from bamboo.bkn.ingest import create_ingest_draft, submit_ingest_draft
from bamboo.bkn.loader import load_bkn_definition
from bamboo.bkn.validator import BKNValidationError


def test_create_ingest_draft_writes_only_draft_files(tmp_path: Path) -> None:
    result = create_ingest_draft(
        platform_id="billing",
        manifest_draft={"name": "Billing", "domain": "billing", "owners": ["@tester"]},
        schema={"classes": {"Customer": {"actions": []}}},
        nodes=[{"id": "customer:c001", "ontology_class": "Customer", "name": "Customer C001"}],
        edges=[],
        inputs=[{"kind": "schema_doc", "title": "entities"}],
        bkn_root=tmp_path,
    )

    draft_root = Path(result["draft_root"])
    assert (draft_root / "manifest.draft.yaml").is_file()
    assert (draft_root / "schema.draft.json").is_file()
    assert (draft_root / "BKN.md").is_file()
    assert (draft_root / "preview.md").is_file()
    assert not (tmp_path / "platforms" / "billing" / "manifest.yaml").exists()


def test_create_ingest_draft_rejects_existing_active_platform(tmp_path: Path) -> None:
    platform_root = tmp_path / "platforms" / "billing"
    platform_root.mkdir(parents=True)
    (platform_root / "manifest.yaml").write_text("platform_id: billing\n", encoding="utf-8")

    with pytest.raises(BKNValidationError, match="active platform already exists"):
        create_ingest_draft(platform_id="billing", bkn_root=tmp_path)


def test_submit_ingest_draft_promotes_files_and_initializes_graph(tmp_path: Path) -> None:
    create_ingest_draft(
        platform_id="billing",
        manifest_draft={"name": "Billing", "domain": "billing", "owners": ["@tester"], "status": "active"},
        schema={"classes": {"Customer": {"actions": []}}},
        nodes=[{"id": "customer:c001", "ontology_class": "Customer", "name": "Customer C001"}],
        edges=[],
        bkn_root=tmp_path,
    )

    result = submit_ingest_draft(platform_id="billing", approve=True, bkn_root=tmp_path)

    platform_root = tmp_path / "platforms" / "billing"
    assert result["submitted"] is True
    assert (platform_root / "manifest.yaml").is_file()
    assert (platform_root / "schema.json").is_file()
    assert (platform_root / "BKN.md").is_file()
    assert not (platform_root / "draft").exists()
    assert (platform_root / "graph.sqlite").is_file()
    assert load_bkn_definition(platform_root).name == "billing"


def test_create_ingest_draft_accepts_custom_bkn_doc(tmp_path: Path) -> None:
    result = create_ingest_draft(
        platform_id="billing",
        bkn_doc="# BKN: billing\n\nUse for subscription billing questions.",
        bkn_root=tmp_path,
    )

    content = (Path(result["draft_root"]) / "BKN.md").read_text(encoding="utf-8")
    assert "Use for subscription billing questions." in content


def test_submit_ingest_draft_approve_false_does_not_submit(tmp_path: Path) -> None:
    create_ingest_draft(platform_id="billing", bkn_root=tmp_path)

    result = submit_ingest_draft(platform_id="billing", approve=False, bkn_root=tmp_path)

    assert result["submitted"] is False
    assert (tmp_path / "platforms" / "billing" / "draft").exists()
