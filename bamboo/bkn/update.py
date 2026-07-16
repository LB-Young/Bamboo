"""Controlled BKN update operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from bamboo.bkn.graph import BknGraph
from bamboo.bkn.ingest import _edge_from_doc, _node_from_doc, _validate_platform_id
from bamboo.bkn.manifest_io import read_manifest, read_schema, validate_manifest_schema_match
from bamboo.bkn.validator import BKNValidationError
from bamboo.userspace.userspace import get_user_bkn_dir


def update_manifest(*, platform_id: str, updates: dict[str, Any], bkn_root: Path | None = None) -> dict[str, Any]:
    """Update writable manifest fields for an active platform."""
    _validate_platform_id(platform_id)
    root = bkn_root or get_user_bkn_dir()
    platform_root = root / "platforms" / platform_id
    manifest_path = platform_root / "manifest.yaml"
    manifest = read_manifest(manifest_path)
    if not manifest.is_writeable():
        raise BKNValidationError(f"{manifest_path}: manifest status {manifest.status} is not writeable")
    allowed = {
        "status",
        "description",
        "domain",
        "owners",
        "data_source_kind",
        "cacheable",
        "operator_allowlist",
        "action_allowlist",
        "cross_platform_edges_allowed",
    }
    rejected = sorted(set(updates) - allowed)
    if rejected:
        raise BKNValidationError(f"{manifest_path}: unsupported manifest fields: {', '.join(rejected)}")
    document = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    document.update({key: value for key, value in updates.items() if key in allowed})
    tmp_path = manifest_path.with_suffix(".yaml.tmp")
    tmp_path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    updated = read_manifest(tmp_path)
    validate_manifest_schema_match(updated, read_schema(platform_root / "schema.json"), schema_path=platform_root / "schema.json")
    tmp_path.replace(manifest_path)
    return {"platform_id": platform_id, "updated_fields": sorted(updates)}


def update_topology(
    *,
    platform_id: str,
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
    evidence: list[str] | None = None,
    bkn_root: Path | None = None,
) -> dict[str, Any]:
    """Update skeleton topology after validating manifest status and evidence."""
    _validate_platform_id(platform_id)
    if not evidence:
        raise BKNValidationError("topology updates require evidence")
    root = bkn_root or get_user_bkn_dir()
    platform_root = root / "platforms" / platform_id
    manifest = read_manifest(platform_root / "manifest.yaml")
    if not manifest.is_writeable():
        raise BKNValidationError(f"{platform_root / 'manifest.yaml'}: manifest status {manifest.status} is not writeable")
    graph = BknGraph(root=platform_root, platform_id=platform_id)
    node_count = 0
    edge_count = 0
    for node_doc in nodes or []:
        graph.upsert_node(_node_from_doc(platform_id, {**node_doc, "evidence": evidence}))
        node_count += 1
    for edge_doc in edges or []:
        graph.upsert_edge(_edge_from_doc(edge_doc))
        edge_count += 1
    _append_update_audit(platform_root / "events.jsonl", {"action": "topology.updated", "evidence": evidence})
    return {"platform_id": platform_id, "nodes": node_count, "edges": edge_count}


def _append_update_audit(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
