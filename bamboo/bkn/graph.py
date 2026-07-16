"""SQLite skeleton graph for platform BKNs."""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bamboo.bkn.events import topology_event
from bamboo.bkn.models import BknDataSourceRef, BknEdge, BknEdgeId, BknNode, BknNodeId, NodeKind


class BknGraph:
    """SQLite-backed topology store."""

    def __init__(self, *, root: Path, platform_id: str = "") -> None:
        self.root = root
        self.platform_id = platform_id
        self.db_path = root / "graph.sqlite"
        self.events_path = root / "events.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert_node(self, node: BknNode) -> BknNode:
        """Insert or replace a skeleton node."""
        now = datetime.now(UTC).isoformat()
        created_at = node.created_at.isoformat()
        updated_at = node.updated_at.isoformat() if node.updated_at else now
        with self._connect() as connection:
            existing = connection.execute("SELECT created_at FROM nodes WHERE id = ?", (node.id.value,)).fetchone()
            connection.execute(
                """
                INSERT INTO nodes (
                    id, platform_id, kind, ontology_class, name, aliases, description, static_attrs,
                    data_source, evidence_ids, confidence, created_at, updated_at, version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    platform_id=excluded.platform_id,
                    kind=excluded.kind,
                    ontology_class=excluded.ontology_class,
                    name=excluded.name,
                    aliases=excluded.aliases,
                    description=excluded.description,
                    static_attrs=excluded.static_attrs,
                    data_source=excluded.data_source,
                    evidence_ids=excluded.evidence_ids,
                    confidence=excluded.confidence,
                    updated_at=excluded.updated_at,
                    version=nodes.version + 1
                """,
                (
                    node.id.value,
                    node.platform_id,
                    node.kind.value,
                    node.ontology_class,
                    node.name,
                    json.dumps(list(node.aliases), ensure_ascii=False),
                    node.description,
                    json.dumps(dict(node.static_attrs), ensure_ascii=False, sort_keys=True),
                    _dump_data_source(node.data_source),
                    json.dumps([item.value for item in node.evidence_ids], ensure_ascii=False),
                    node.confidence,
                    existing["created_at"] if existing else created_at,
                    updated_at,
                    node.version,
                ),
            )
        self._append_event("node.upserted", {"id": node.id.value})
        stored = self.get_node(node.id)
        return stored if stored is not None else node

    def upsert_edge(self, edge: BknEdge) -> BknEdge:
        """Insert or replace a skeleton edge."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO edges (id, src, dst, relation, weight, evidence_ids, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    src=excluded.src,
                    dst=excluded.dst,
                    relation=excluded.relation,
                    weight=excluded.weight,
                    evidence_ids=excluded.evidence_ids
                """,
                (
                    edge.id.value,
                    edge.src.value,
                    edge.dst.value,
                    edge.relation,
                    edge.weight,
                    json.dumps([item.value for item in edge.evidence_ids], ensure_ascii=False),
                    edge.created_at.isoformat(),
                ),
            )
        self._append_event("edge.upserted", {"id": edge.id.value, "src": edge.src.value, "dst": edge.dst.value})
        return self.get_edge(edge.id) or edge

    def get_node(self, node_id: BknNodeId) -> BknNode | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM nodes WHERE id = ?", (node_id.value,)).fetchone()
        return _row_to_node(row) if row else None

    def get_edge(self, edge_id: BknEdgeId) -> BknEdge | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM edges WHERE id = ?", (edge_id.value,)).fetchone()
        return _row_to_edge(row) if row else None

    def find_nodes(
        self,
        *,
        name: str | None = None,
        kind: NodeKind | None = None,
        ontology_class: str | None = None,
        alias: str | None = None,
    ) -> list[BknNode]:
        clauses: list[str] = []
        params: list[Any] = []
        if name:
            clauses.append("LOWER(name) LIKE ?")
            params.append(f"%{name.lower()}%")
        if kind:
            clauses.append("kind = ?")
            params.append(kind.value)
        if ontology_class:
            clauses.append("ontology_class = ?")
            params.append(ontology_class)
        sql = "SELECT * FROM nodes"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id"
        with self._connect() as connection:
            nodes = [_row_to_node(row) for row in connection.execute(sql, params).fetchall()]
        if alias:
            return [node for node in nodes if alias in node.aliases]
        return nodes

    def neighborhood(self, node_id: BknNodeId, *, depth: int = 1, ontology_class: str | None = None) -> list[BknEdge]:
        if depth <= 0:
            return []
        seen_nodes = {node_id.value}
        seen_edges: set[str] = set()
        frontier: deque[tuple[str, int]] = deque([(node_id.value, 0)])
        edges: list[BknEdge] = []
        with self._connect() as connection:
            while frontier:
                current, level = frontier.popleft()
                if level >= depth:
                    continue
                rows = connection.execute(
                    "SELECT * FROM edges WHERE src = ? OR dst = ? ORDER BY id",
                    (current, current),
                ).fetchall()
                for row in rows:
                    edge = _row_to_edge(row)
                    if edge.id.value not in seen_edges:
                        if ontology_class is None or _edge_touches_class(connection, edge, ontology_class):
                            edges.append(edge)
                        seen_edges.add(edge.id.value)
                    other = edge.dst.value if edge.src.value == current else edge.src.value
                    if other not in seen_nodes:
                        seen_nodes.add(other)
                        frontier.append((other, level + 1))
        return edges

    def subgraph(self, node_id: BknNodeId | None = None, *, depth: int = 1) -> tuple[list[BknNode], list[BknEdge]]:
        """Return nodes and edges for a full graph or one node-centered neighborhood."""
        if node_id is None:
            return self.find_nodes(), self.list_edges()
        root_node = self.get_node(node_id)
        if root_node is None:
            return [], []
        edges = self.neighborhood(node_id, depth=depth)
        node_ids = {node_id.value}
        for edge in edges:
            node_ids.add(edge.src.value)
            node_ids.add(edge.dst.value)
        nodes = []
        for value in sorted(node_ids):
            node = self.get_node(BknNodeId(value))
            if node is not None:
                nodes.append(node)
        return nodes, edges

    def path(self, src: BknNodeId, dst: BknNodeId, *, max_depth: int = 4) -> list[BknEdge]:
        if src.value == dst.value:
            return []
        frontier: deque[tuple[str, list[BknEdge]]] = deque([(src.value, [])])
        seen = {src.value}
        with self._connect() as connection:
            while frontier:
                current, path = frontier.popleft()
                if len(path) >= max_depth:
                    continue
                rows = connection.execute(
                    "SELECT * FROM edges WHERE src = ? OR dst = ? ORDER BY id",
                    (current, current),
                ).fetchall()
                for row in rows:
                    edge = _row_to_edge(row)
                    other = edge.dst.value if edge.src.value == current else edge.src.value
                    next_path = [*path, edge]
                    if other == dst.value:
                        return next_path
                    if other not in seen:
                        seen.add(other)
                        frontier.append((other, next_path))
        return []

    def search_by_text(self, query: str, *, limit: int = 10) -> list[BknNode]:
        pattern = f"%{query.lower()}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM nodes
                WHERE LOWER(id) LIKE ? OR LOWER(name) LIKE ? OR LOWER(description) LIKE ?
                ORDER BY id
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            ).fetchall()
        return [_row_to_node(row) for row in rows]

    def list_edges(self) -> list[BknEdge]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM edges ORDER BY id").fetchall()
        return [_row_to_edge(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    platform_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    ontology_class TEXT NOT NULL,
                    name TEXT NOT NULL,
                    aliases TEXT NOT NULL,
                    description TEXT NOT NULL,
                    static_attrs TEXT NOT NULL,
                    data_source TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    src TEXT NOT NULL,
                    dst TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_nodes_text ON nodes(name, description)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst)")

    def _append_event(self, action: str, payload: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(topology_event(action=action, payload=payload), ensure_ascii=False) + "\n")


def _dump_data_source(ref: BknDataSourceRef | None) -> str:
    if ref is None:
        return "{}"
    return json.dumps(
        {
            "kind": ref.kind,
            "location": ref.location,
            "field_mapping": dict(ref.field_mapping),
            "cacheable": ref.cacheable,
            "cache_key": ref.cache_key,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _row_to_node(row: sqlite3.Row) -> BknNode:
    data_source = json.loads(row["data_source"])
    evidence_ids = tuple(BknNodeId(value) for value in json.loads(row["evidence_ids"]))
    return BknNode(
        id=BknNodeId(row["id"]),
        platform_id=row["platform_id"],
        kind=NodeKind(row["kind"]),
        ontology_class=row["ontology_class"],
        name=row["name"],
        aliases=tuple(json.loads(row["aliases"])),
        description=row["description"],
        static_attrs=json.loads(row["static_attrs"]),
        data_source=_row_data_source(data_source),
        evidence_ids=evidence_ids,
        confidence=float(row["confidence"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        version=int(row["version"]),
    )


def _row_to_edge(row: sqlite3.Row) -> BknEdge:
    return BknEdge(
        id=BknEdgeId(row["id"]),
        src=BknNodeId(row["src"]),
        dst=BknNodeId(row["dst"]),
        relation=row["relation"],
        weight=float(row["weight"]),
        evidence_ids=tuple(BknNodeId(value) for value in json.loads(row["evidence_ids"])),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_data_source(value: dict[str, Any]) -> BknDataSourceRef | None:
    if not value:
        return None
    return BknDataSourceRef(
        kind=value.get("kind", "static"),
        location=value.get("location", ""),
        field_mapping=value.get("field_mapping", {}),
        cacheable=bool(value.get("cacheable", False)),
        cache_key=value.get("cache_key"),
    )


def _edge_touches_class(connection: sqlite3.Connection, edge: BknEdge, ontology_class: str) -> bool:
    rows = connection.execute(
        "SELECT ontology_class FROM nodes WHERE id IN (?, ?)",
        (edge.src.value, edge.dst.value),
    ).fetchall()
    return any(row["ontology_class"] == ontology_class for row in rows)
