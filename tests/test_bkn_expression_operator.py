"""Tests for safe BKN expression operators."""

from __future__ import annotations

from pathlib import Path

import pytest

from bamboo.bkn.loader import BknLoader, load_bkn_definition
from bamboo.bkn.operators.expression import evaluate_expression_operator

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bkn" / "personal-media"


def test_expression_operator_evaluates_roi() -> None:
    assert evaluate_expression_operator("(stars + forks) / max(views, 1)", {"stars": 42, "forks": 6, "views": 1800}) > 0


def test_expression_operator_rejects_imports() -> None:
    with pytest.raises(ValueError, match="safe built-in|unsupported expression node"):
        evaluate_expression_operator("__import__('os').system('echo no')", {})


def test_bkn_loader_places_expression_output_in_snapshot() -> None:
    definition = load_bkn_definition(FIXTURE_ROOT)

    snapshot = BknLoader(definition).load(focus=("content:agent-memory-design",), run_operators=("calculate_content_roi",))

    assert snapshot.operator_outputs["content:agent-memory-design"]["calculate_content_roi"] == pytest.approx(0.0266666666)
