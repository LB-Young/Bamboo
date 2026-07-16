"""Read-only local source readers for BKN retrieval."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from bamboo.bkn.models import BKNEntity, BKNSource


def load_dynamic_data(
    *,
    root: Path,
    entity: BKNEntity,
    sources: dict[str, BKNSource],
    suppress_errors: bool = True,
) -> dict[str, Any]:
    """Load dynamic data for an entity from its configured source, if present."""
    data = dict(entity.properties)
    source_name = entity.properties.get("source")
    if not isinstance(source_name, str) or source_name not in sources:
        return data
    source = sources[source_name]
    try:
        loaded = _read_source(root=root, source=source, entity=entity)
    except (OSError, ValueError, sqlite3.Error):
        if suppress_errors:
            return data
        raise
    data.update(loaded)
    return data


def _read_source(*, root: Path, source: BKNSource, entity: BKNEntity) -> dict[str, Any]:
    if source.source_type == "static":
        values = source.config.get("values", {})
        return values if isinstance(values, dict) else {}
    if source.source_type == "json":
        return _read_json_source(root=root, source=source, entity=entity)
    if source.source_type == "csv":
        return _read_csv_source(root=root, source=source, entity=entity)
    if source.source_type == "sqlite":
        return _read_sqlite_source(root=root, source=source, entity=entity)
    if source.source_type == "file":
        path = _safe_path(root, str(source.config.get("path", "")))
        return {"content": path.read_text(encoding="utf-8")}
    return {}


def _read_json_source(*, root: Path, source: BKNSource, entity: BKNEntity) -> dict[str, Any]:
    path = _safe_path(root, str(source.config.get("path", "")))
    document = json.loads(path.read_text(encoding="utf-8"))
    key = source.config.get("key", "id")
    if isinstance(document, list):
        for item in document:
            if isinstance(item, dict) and item.get(key) == entity.id:
                return dict(item)
        return {}
    if isinstance(document, dict):
        value = document.get(entity.id)
        if isinstance(value, dict):
            return value
    return {}


def _read_csv_source(*, root: Path, source: BKNSource, entity: BKNEntity) -> dict[str, Any]:
    path = _safe_path(root, str(source.config.get("path", "")))
    key = str(source.config.get("key", "id"))
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get(key) == entity.id:
                return dict(row)
    return {}


def _read_sqlite_source(*, root: Path, source: BKNSource, entity: BKNEntity) -> dict[str, Any]:
    path = _safe_path(root, str(source.config.get("path", "")))
    table = str(source.config.get("table", ""))
    key = str(source.config.get("key", "id"))
    if not table.isidentifier() or not key.isidentifier():
        raise ValueError("sqlite table and key must be identifiers")
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(f"SELECT * FROM {table} WHERE {key} = ? LIMIT 1", (entity.id,)).fetchone()
    return dict(row) if row is not None else {}


def _safe_path(root: Path, value: str) -> Path:
    path = (root / value).expanduser().resolve()
    root_resolved = root.resolve()
    if path != root_resolved and root_resolved not in path.parents:
        raise ValueError(f"path escapes BKN root: {value}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path
