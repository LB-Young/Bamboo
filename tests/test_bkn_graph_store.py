"""Tests for SQLite BKN graph store."""

from __future__ import annotations

from pathlib import Path

from bamboo.bkn.graph import BknGraph
from bamboo.bkn.models import BknEdge, BknEdgeId, BknNode, BknNodeId, NodeKind


def test_bkn_graph_upserts_nodes_and_edges(tmp_path: Path) -> None:
    graph = BknGraph(root=tmp_path, platform_id="billing")
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
    )

    stored_customer = graph.upsert_node(customer)
    graph.upsert_node(invoice)
    edge = graph.upsert_edge(
        BknEdge(
            id=BknEdgeId("edge:customer-invoice"),
            src=customer.id,
            dst=invoice.id,
            relation="HAS_INVOICE",
        )
    )

    assert stored_customer.version == 1
    assert graph.get_node(customer.id).name == "Customer C001"  # type: ignore[union-attr]
    assert edge.relation == "HAS_INVOICE"
    assert [item.id.value for item in graph.neighborhood(customer.id, depth=1)] == ["edge:customer-invoice"]
    assert [item.id.value for item in graph.path(customer.id, invoice.id)] == ["edge:customer-invoice"]
    assert "node.upserted" in (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "edge.upserted" in (tmp_path / "events.jsonl").read_text(encoding="utf-8")


def test_bkn_graph_upsert_node_is_idempotent_and_versions(tmp_path: Path) -> None:
    graph = BknGraph(root=tmp_path, platform_id="billing")
    node = BknNode(
        id=BknNodeId("customer:c001"),
        platform_id="billing",
        kind=NodeKind.ENTITY,
        ontology_class="Customer",
        name="Customer C001",
    )

    graph.upsert_node(node)
    updated = graph.upsert_node(
        BknNode(
            id=node.id,
            platform_id="billing",
            kind=NodeKind.ENTITY,
            ontology_class="Customer",
            name="Customer C001 Updated",
        )
    )

    assert updated.version == 2
    assert graph.search_by_text("updated")[0].id.value == "customer:c001"
