"""Draft and submit platform BKN packages."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from bamboo.bkn.graph import BknGraph
from bamboo.bkn.manifest_io import read_manifest, read_schema, validate_manifest_schema_match
from bamboo.bkn.models import BknEdge, BknEdgeId, BknNode, BknNodeId, NodeKind
from bamboo.bkn.validator import BKNValidationError
from bamboo.userspace.userspace import get_user_bkn_dir


def create_ingest_draft(
    *,
    platform_id: str,
    manifest_draft: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
    inputs: list[dict[str, Any]] | None = None,
    bkn_root: Path | None = None,
) -> dict[str, Any]:
    """Create a staged BKN draft without touching the active platform files."""
    _validate_platform_id(platform_id)
    root = bkn_root or get_user_bkn_dir()
    platform_root = root / "platforms" / platform_id
    if (platform_root / "manifest.yaml").exists():
        raise BKNValidationError(f"{platform_root}: active platform already exists")
    draft_root = platform_root / "draft"
    draft_root.mkdir(parents=True, exist_ok=True)

    manifest = _manifest_document(platform_id, manifest_draft or {})
    schema_document = _schema_document(platform_id, schema or {}, nodes or [], edges or [])
    manifest_path = draft_root / "manifest.draft.yaml"
    schema_path = draft_root / "schema.draft.json"
    nodes_path = draft_root / "nodes.draft.json"
    edges_path = draft_root / "edges.draft.json"
    preview_path = draft_root / "preview.md"
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    schema_path.write_text(json.dumps(schema_document, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    nodes_path.write_text(json.dumps(nodes or [], ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    edges_path.write_text(json.dumps(edges or [], ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    preview_path.write_text(_preview(platform_id, manifest, schema_document, nodes or [], edges or [], inputs or []), encoding="utf-8")
    return {
        "platform_id": platform_id,
        "draft_root": str(draft_root),
        "manifest_path": str(manifest_path),
        "schema_path": str(schema_path),
        "preview_path": str(preview_path),
    }


def submit_ingest_draft(
    *,
    platform_id: str,
    approve: bool,
    edits: dict[str, Any] | None = None,
    bkn_root: Path | None = None,
) -> dict[str, Any]:
    """Submit a staged BKN draft into the active platform directory."""
    _validate_platform_id(platform_id)
    root = bkn_root or get_user_bkn_dir()
    platform_root = root / "platforms" / platform_id
    draft_root = platform_root / "draft"
    if not approve:
        return {"platform_id": platform_id, "submitted": False, "reason": "approve=false"}
    if not draft_root.is_dir():
        raise BKNValidationError(f"{draft_root}: draft does not exist")
    manifest = yaml.safe_load((draft_root / "manifest.draft.yaml").read_text(encoding="utf-8")) or {}
    schema = json.loads((draft_root / "schema.draft.json").read_text(encoding="utf-8"))
    if edits:
        manifest.update(edits.get("manifest", {}))
        schema.update(edits.get("schema", {}))

    tmp_root = platform_root / ".submit-tmp"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)
    (tmp_root / "manifest.yaml").write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (tmp_root / "schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if (draft_root / "preview.md").exists():
        shutil.copy2(draft_root / "preview.md", tmp_root / "preview.md")
    read_manifest(tmp_root / "manifest.yaml")
    validate_manifest_schema_match(read_manifest(tmp_root / "manifest.yaml"), read_schema(tmp_root / "schema.json"), schema_path=tmp_root / "schema.json")

    for name in ("manifest.yaml", "schema.json", "preview.md"):
        source = tmp_root / name
        if source.exists():
            source.replace(platform_root / name)
    graph = BknGraph(root=platform_root, platform_id=platform_id)
    for node_doc in _json_list(draft_root / "nodes.draft.json"):
        graph.upsert_node(_node_from_doc(platform_id, node_doc))
    for edge_doc in _json_list(draft_root / "edges.draft.json"):
        graph.upsert_edge(_edge_from_doc(edge_doc))
    shutil.rmtree(tmp_root)
    shutil.rmtree(draft_root)
    return {"platform_id": platform_id, "submitted": True, "platform_root": str(platform_root)}


def _manifest_document(platform_id: str, draft: dict[str, Any]) -> dict[str, Any]:
    document = {
        "platform_id": platform_id,
        "name": draft.get("name", platform_id),
        "domain": draft.get("domain", "general"),
        "owners": draft.get("owners", []),
        "status": draft.get("status", "draft"),
        "data_source_kind": draft.get("data_source_kind", "static"),
        "cacheable": bool(draft.get("cacheable", False)),
        "operator_allowlist": draft.get("operator_allowlist", []),
        "action_allowlist": draft.get("action_allowlist", []),
        "cross_platform_edges_allowed": bool(draft.get("cross_platform_edges_allowed", False)),
        "description": draft.get("description", ""),
    }
    if not document["owners"]:
        document["owners"] = ["@local"]
    return document


def _schema_document(platform_id: str, schema: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    classes = schema.get("classes")
    if not isinstance(classes, dict):
        classes = {str(node.get("ontology_class", "Entity")): {"operators": [], "actions": []} for node in nodes}
    relations = schema.get("relations")
    if not isinstance(relations, dict):
        relations = {str(edge.get("relation", "RELATED_TO")): {} for edge in edges}
    return {
        "platform_id": platform_id,
        "version": int(schema.get("version", 1)),
        "classes": classes,
        "relations": relations,
        "operator_registry": schema.get("operator_registry", {}),
        "action_registry": schema.get("action_registry", {}),
    }


def _preview(
    platform_id: str,
    manifest: dict[str, Any],
    schema: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    inputs: list[dict[str, Any]],
) -> str:
    lines = [
        f"# BKN Draft: {platform_id}",
        "",
        f"- Name: {manifest.get('name', platform_id)}",
        f"- Domain: {manifest.get('domain', '')}",
        f"- Status: {manifest.get('status', 'draft')}",
        f"- Classes: {', '.join(sorted(schema.get('classes', {})))}",
        f"- Nodes: {len(nodes)}",
        f"- Edges: {len(edges)}",
    ]
    if inputs:
        lines.extend(["", "## Inputs"])
        lines.extend(f"- {item.get('kind', 'unknown')}: {item.get('title', '')}" for item in inputs)
    if edges:
        lines.extend(["", "## Graph", "", "```mermaid", "flowchart LR"])
        for edge in edges:
            lines.append(f"  { _mermaid_id(edge.get('src') or edge.get('from')) } -->|{edge.get('relation', 'RELATED_TO')}| { _mermaid_id(edge.get('dst') or edge.get('to')) }")
        lines.append("```")
    return "\n".join(lines) + "\n"


def _node_from_doc(platform_id: str, doc: dict[str, Any]) -> BknNode:
    node_id = str(doc.get("id", ""))
    if not node_id:
        raise BKNValidationError("node id is required")
    return BknNode(
        id=BknNodeId(node_id),
        platform_id=platform_id,
        kind=NodeKind(str(doc.get("kind", "entity"))),
        ontology_class=str(doc.get("ontology_class", doc.get("class", "Entity"))),
        name=str(doc.get("name", node_id)),
        aliases=tuple(item for item in doc.get("aliases", []) if isinstance(item, str)),
        description=str(doc.get("description", "")),
        static_attrs={key: value for key, value in doc.items() if key not in {"id", "kind", "ontology_class", "class", "name", "aliases", "description"}},
    )


def _edge_from_doc(doc: dict[str, Any]) -> BknEdge:
    src = str(doc.get("src", doc.get("from", "")))
    dst = str(doc.get("dst", doc.get("to", "")))
    relation = str(doc.get("relation", doc.get("type", "")))
    if not src or not dst or not relation:
        raise BKNValidationError("edge src/dst/relation are required")
    edge_id = str(doc.get("id", f"edge:{src}:{relation}:{dst}"))
    return BknEdge(id=BknEdgeId(edge_id), src=BknNodeId(src), dst=BknNodeId(dst), relation=relation)


def _json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _validate_platform_id(platform_id: str) -> None:
    if not platform_id or not platform_id.replace("_", "").replace("-", "").isalnum():
        raise BKNValidationError("platform_id must contain only letters, numbers, hyphen, or underscore")


def _mermaid_id(value: Any) -> str:
    return str(value or "unknown").replace(":", "_").replace("-", "_")
