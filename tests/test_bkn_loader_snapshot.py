"""Tests for BKN Context Loader snapshots."""

from __future__ import annotations

import json
from pathlib import Path

from bamboo.bkn.graph import BknGraph
from bamboo.bkn.loader import BknLoader, load_bkn_definition
from bamboo.bkn.models import BknEdge, BknEdgeId, BknNode, BknNodeId, NodeKind
from bamboo.bkn.prompt_render import render_bkn_snapshot


def test_bkn_loader_builds_snapshot_and_filters_actions_by_manifest(tmp_path: Path) -> None:
    root = _platform_fixture(tmp_path, action_allowlist=["SyncToErp"])
    graph = BknGraph(root=root, platform_id="billing")
    customer = BknNode(
        id=BknNodeId("customer:c001"),
        platform_id="billing",
        kind=NodeKind.ENTITY,
        ontology_class="Customer",
        name="Customer C001",
        static_attrs={"customer_no": "C001"},
    )
    invoice = BknNode(
        id=BknNodeId("invoice:i001"),
        platform_id="billing",
        kind=NodeKind.ENTITY,
        ontology_class="Invoice",
        name="Invoice I001",
        static_attrs={"invoice_no": "I001"},
    )
    graph.upsert_node(customer)
    graph.upsert_node(invoice)
    graph.upsert_edge(
        BknEdge(
            id=BknEdgeId("edge:c001-i001"),
            src=customer.id,
            dst=invoice.id,
            relation="HAS_INVOICE",
        )
    )
    definition = load_bkn_definition(root)

    snapshot = BknLoader(definition).load(focus=("customer:c001",), depth=1)

    assert snapshot.platform_id == "billing"
    assert snapshot.manifest_status == "active"
    assert snapshot.skeleton == ("(customer:c001)-[HAS_INVOICE]->(invoice:i001)",)
    assert snapshot.static_attrs["customer:c001"]["customer_no"] == "C001"
    assert snapshot.operator_outputs["invoice:i001"]["Calculate_MRR"] == "bamboo.bkn.operators.billing.mrr"
    assert [action.name for action in snapshot.available_actions] == ["SyncToErp"]
    assert "BKN Context" in render_bkn_snapshot(snapshot)


def test_bkn_loader_marks_attrs_unavailable_without_failing(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    (root / "schema").mkdir(parents=True)
    (root / "graph").mkdir()
    (root / "sources").mkdir()
    root.joinpath("bkn.yaml").write_text("schema_version: 1\nname: legacy\n", encoding="utf-8")
    root.joinpath("schema", "ontology.yaml").write_text("classes:\n  Content: {}\nrelations: {}\n", encoding="utf-8")
    root.joinpath("graph", "entities.yaml").write_text(
        "entities:\n  - id: content:missing\n    class: Content\n    source: missing_json\n",
        encoding="utf-8",
    )
    root.joinpath("graph", "relations.yaml").write_text("relations: []\n", encoding="utf-8")
    root.joinpath("sources", "platforms.yaml").write_text(
        "sources:\n  missing_json:\n    type: json\n    path: data/missing.json\n",
        encoding="utf-8",
    )
    definition = load_bkn_definition(root)

    snapshot = BknLoader(definition).load(focus=("content:missing",), include_attrs=True)

    assert snapshot.attrs_unavailable == ("content:missing",)
    assert snapshot.static_attrs["content:missing"]["source"] == "missing_json"


def _platform_fixture(tmp_path: Path, *, action_allowlist: list[str]) -> Path:
    root = tmp_path / "billing"
    root.mkdir()
    root.joinpath("manifest.yaml").write_text(
        "\n".join(
            [
                "platform_id: billing",
                "name: Billing Platform",
                "domain: billing",
                "owners:",
                '  - "@tester"',
                "status: active",
                "data_source_kind: static",
                "action_allowlist:",
                *(f"  - {item}" for item in action_allowlist),
                "",
            ]
        ),
        encoding="utf-8",
    )
    root.joinpath("schema.json").write_text(
        json.dumps(
            {
                "platform_id": "billing",
                "version": 1,
                "classes": {
                    "Customer": {"static_attrs": ["customer_no"], "operators": [], "actions": []},
                    "Invoice": {"static_attrs": ["invoice_no"], "operators": ["Calculate_MRR"], "actions": ["SyncToErp", "Refund"]},
                },
                "relations": {"HAS_INVOICE": {"from": "Customer", "to": "Invoice"}},
                "operator_registry": {"Calculate_MRR": "bamboo.bkn.operators.billing.mrr"},
                "action_registry": {
                    "SyncToErp": {"tool": "workflow_run", "description": "Sync invoice to ERP"},
                    "Refund": {"tool": "workflow_run", "description": "Refund invoice"},
                },
            }
        ),
        encoding="utf-8",
    )
    return root
