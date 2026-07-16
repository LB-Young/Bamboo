"""Runtime storage for BKN indexes and audit events."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bamboo.bkn.models import BKNDefinition
from bamboo.userspace.userspace import get_bkn_storage_dir


class BKNStore:
    """Persist lightweight BKN indexes and refresh state."""

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or get_bkn_storage_dir()
        self.index_dir = self.root / "indexes"
        self.cache_dir = self.root / "cache"
        self.audit_path = self.root / "audit.jsonl"
        self.state_path = self.root / "state.json"

    def ensure(self) -> None:
        """Create storage directories."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def write_index(self, definition: BKNDefinition) -> None:
        """Write a deterministic lightweight index for one loaded BKN."""
        self.ensure()
        payload = {
            "network": definition.name,
            "indexed_at": _utc_now(),
            "entities": {
                entity_id: {
                    "class": entity.entity_class,
                    "title": entity.title,
                    "keywords": _keywords_for_entity(entity_id, entity.properties),
                }
                for entity_id, entity in sorted(definition.entities.items())
            },
            "adjacency": _adjacency(definition),
        }
        (self.index_dir / f"{definition.name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def write_state(self, state: dict[str, Any]) -> None:
        """Write registry state."""
        self.ensure()
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def append_audit(self, event: dict[str, Any]) -> None:
        """Append one audit event."""
        self.ensure()
        payload = {"time": _utc_now(), **event}
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _adjacency(definition: BKNDefinition) -> dict[str, list[dict[str, str]]]:
    adjacency: dict[str, list[dict[str, str]]] = {}
    for relation in definition.relations:
        adjacency.setdefault(relation.from_id, []).append({"type": relation.relation_type, "to": relation.to_id})
        adjacency.setdefault(relation.to_id, []).append({"type": relation.relation_type, "from": relation.from_id})
    return {key: value for key, value in sorted(adjacency.items())}


def _keywords_for_entity(entity_id: str, properties: dict[str, Any]) -> list[str]:
    text = " ".join([entity_id, *(str(value) for value in properties.values())]).lower()
    return sorted({part.strip(".,:;()[]{}") for part in text.split() if part.strip(".,:;()[]{}")})


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
