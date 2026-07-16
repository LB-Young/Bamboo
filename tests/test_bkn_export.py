"""Tests for BKN graph export."""

from __future__ import annotations

from pathlib import Path

from bamboo.bkn.export import export_bkn
from bamboo.bkn.loader import load_bkn_definition
from bamboo.bkn.models import BKNDefinition

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bkn" / "personal-media"


def test_export_bkn_mermaid_is_stable() -> None:
    definition = load_bkn_definition(FIXTURE_ROOT)

    assert export_bkn(definition, output_format="mermaid") == "\n".join(
        [
            "flowchart LR",
            '  content_agent_memory_design["Agent Memory Design Notes"]',
            '  platform_github["GitHub"]',
            '  tag_ai_agent["AI Agent"]',
            "  content_agent_memory_design -->|PUBLISHED_ON| platform_github",
            "  content_agent_memory_design -->|TAGGED_WITH| tag_ai_agent",
        ]
    )


def test_export_bkn_dot_and_markdown_subgraph() -> None:
    definition = load_bkn_definition(FIXTURE_ROOT)

    dot = export_bkn(definition, output_format="dot", node="content:agent-memory-design", depth=1)
    markdown = export_bkn(definition, output_format="markdown", node="content:agent-memory-design", depth=0)

    assert '"content:agent-memory-design" -> "platform:github" [label="PUBLISHED_ON"];' in dot
    assert '"content:agent-memory-design" -> "tag:ai-agent" [label="TAGGED_WITH"];' in dot
    assert "- `content:agent-memory-design` (Content): Agent Memory Design Notes" in markdown
    assert "- No relations." in markdown


def test_export_bkn_empty_graph_has_reasonable_output(tmp_path: Path) -> None:
    definition = BKNDefinition(name="empty", root=tmp_path)

    assert export_bkn(definition, output_format="mermaid") == 'flowchart LR\n  empty["No BKN nodes found for empty"]'
    assert "No BKN nodes found for `empty`." in export_bkn(definition, output_format="markdown")
