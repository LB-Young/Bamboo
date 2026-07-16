"""Read platform BKN manifest and schema files."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from bamboo.bkn.models import BknManifest
from bamboo.bkn.validator import BKNValidationError


def read_manifest(path: Path) -> BknManifest:
    """Read a platform manifest.yaml."""
    document = _read_yaml_mapping(path)
    platform_id = _required_str(document, "platform_id", path)
    name = _required_str(document, "name", path)
    domain = _required_str(document, "domain", path)
    owners = document.get("owners")
    if not isinstance(owners, list) or not all(isinstance(item, str) for item in owners):
        raise BKNValidationError(f"{path}: owners must be a list of strings")
    return BknManifest(
        platform_id=platform_id,
        name=name,
        domain=domain,
        owners=tuple(owners),
        created_at=_parse_datetime(document.get("created_at")),
        updated_at=_parse_datetime(document.get("updated_at")),
        version=int(document.get("version", 1)),
        status=str(document.get("status", "draft")),  # type: ignore[arg-type]
        description=str(document.get("description", "")),
        data_source_kind=str(document.get("data_source_kind", "static")),  # type: ignore[arg-type]
        base_url=str(document.get("base_url", "")),
        auth_ref=str(document.get("auth_ref", "")),
        cacheable=bool(document.get("cacheable", False)),
        cache_strategy=str(document.get("cache_strategy", "ttl")),  # type: ignore[arg-type]
        cache_ttl_seconds=int(document.get("cache_ttl_seconds", 300)),
        operator_allowlist=tuple(_string_list(document.get("operator_allowlist"))),
        action_allowlist=tuple(_string_list(document.get("action_allowlist"))),
        cross_platform_edges_allowed=bool(document.get("cross_platform_edges_allowed", False)),
        source_path=str(path),
    )


def read_schema(path: Path) -> dict[str, Any]:
    """Read schema.json."""
    if not path.is_file():
        raise BKNValidationError(f"{path}: file is required")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BKNValidationError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise BKNValidationError(f"{path}: expected JSON object")
    return document


def validate_manifest_schema_match(manifest: BknManifest, schema: dict[str, Any], *, schema_path: Path) -> None:
    """Ensure manifest and schema target the same platform."""
    schema_platform_id = schema.get("platform_id")
    if schema_platform_id != manifest.platform_id:
        raise BKNValidationError(
            f"{schema_path}: schema platform_id {schema_platform_id!r} does not match manifest platform_id "
            f"{manifest.platform_id!r}"
        )


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BKNValidationError(f"{path}: file is required")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise BKNValidationError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise BKNValidationError(f"{path}: expected YAML mapping")
    return document


def _required_str(document: dict[str, Any], key: str, path: Path) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise BKNValidationError(f"{path}: {key} is required")
    return value


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value)
