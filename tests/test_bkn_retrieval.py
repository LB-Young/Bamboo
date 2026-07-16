"""Tests for BKN retrieval."""

from __future__ import annotations

from pathlib import Path

from bamboo.bkn.loader import load_bkn_definition
from bamboo.bkn.retrieval import render_bkn_results, retrieve_bkn

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bkn" / "personal-media"


def test_retrieve_bkn_matches_title_and_expands_relations() -> None:
    definition = load_bkn_definition(FIXTURE_ROOT)

    matches = retrieve_bkn(query="Agent Memory", definitions=[definition], max_hops=1)

    assert matches
    match = matches[0]
    assert match.entity_id == "content:agent-memory-design"
    assert {relation.relation_type for relation in match.relations} == {"PUBLISHED_ON", "TAGGED_WITH"}
    assert match.dynamic_data["stars"] == 42
    assert match.operators[0].name == "calculate_content_roi"
    assert match.actions[0].name == "republish_content"


def test_retrieve_bkn_respects_zero_hops_and_limit() -> None:
    definition = load_bkn_definition(FIXTURE_ROOT)

    matches = retrieve_bkn(query="Agent", definitions=[definition], limit=1, max_hops=0)

    assert len(matches) == 1
    assert matches[0].relations == ()


def test_render_bkn_results_escapes_and_renders_count() -> None:
    definition = load_bkn_definition(FIXTURE_ROOT)
    matches = retrieve_bkn(query="Agent", definitions=[definition], limit=1)

    rendered = render_bkn_results(query="Agent", network="personal-media", matches=matches)

    assert '<bkn_results query="Agent" network="personal-media" count="1">' in rendered
    assert "content:agent-memory-design -[PUBLISHED_ON]-&gt; platform:github" in rendered
