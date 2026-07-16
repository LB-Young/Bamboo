"""Tests for BKN package loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from bamboo.bkn.loader import load_bkn_definition
from bamboo.bkn.validator import BKNValidationError

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bkn" / "personal-media"


def test_load_bkn_definition_parses_fixture() -> None:
    definition = load_bkn_definition(FIXTURE_ROOT)

    assert definition.name == "personal-media"
    assert definition.enabled is True
    assert "Content" in definition.ontology.classes
    assert "content:agent-memory-design" in definition.entities
    assert definition.entities["content:agent-memory-design"].entity_class == "Content"
    assert definition.relations[0].relation_type == "PUBLISHED_ON"
    assert "github_stats" in definition.sources
    assert "calculate_content_roi" in definition.operators
    assert "republish_content" in definition.actions


def test_load_bkn_definition_rejects_unknown_class(tmp_path: Path) -> None:
    root = tmp_path / "bad-bkn"
    (root / "schema").mkdir(parents=True)
    (root / "graph").mkdir()
    (root / "bkn.yaml").write_text("schema_version: 1\nname: bad\n", encoding="utf-8")
    (root / "schema" / "ontology.yaml").write_text("classes:\n  Content: {}\nrelations: {}\n", encoding="utf-8")
    (root / "graph" / "entities.yaml").write_text(
        "entities:\n  - id: x\n    class: Missing\n",
        encoding="utf-8",
    )
    (root / "graph" / "relations.yaml").write_text("relations: []\n", encoding="utf-8")

    with pytest.raises(BKNValidationError, match="unknown class Missing"):
        load_bkn_definition(root)
