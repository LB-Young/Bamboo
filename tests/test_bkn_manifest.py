"""Tests for platform BKN manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bamboo.bkn.loader import load_bkn_definition
from bamboo.bkn.manifest_io import read_manifest
from bamboo.bkn.registry import BKNRegistry
from bamboo.bkn.store import BKNStore
from bamboo.bkn.validator import BKNValidationError


def test_read_manifest_requires_core_fields(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text("platform_id: billing\nname: Billing\n", encoding="utf-8")

    with pytest.raises(BKNValidationError, match="domain is required"):
        read_manifest(path)


def test_load_platform_bkn_definition_validates_schema_platform_id(tmp_path: Path) -> None:
    root = _platform_root(tmp_path, platform_id="billing")
    (root / "schema.json").write_text(json.dumps({"platform_id": "order", "version": 1, "classes": {}}), encoding="utf-8")

    with pytest.raises(BKNValidationError, match="does not match manifest"):
        load_bkn_definition(root)


def test_registry_scans_platforms_and_skips_paused_by_default(tmp_path: Path) -> None:
    bkn_root = tmp_path / "bkn"
    active = _platform_root(bkn_root / "platforms", platform_id="billing", status="active")
    paused = _platform_root(bkn_root / "platforms", platform_id="support", status="paused")
    _write_schema(active, "billing")
    _write_schema(paused, "support")
    registry = BKNRegistry(bkn_dirs=[bkn_root], store=BKNStore(root=tmp_path / "storage" / "bkn"))

    assert [definition.name for definition in registry.list()] == ["billing"]
    assert [definition.name for definition in registry.list(include_inactive=True)] == ["billing", "support"]


def _platform_root(root: Path, *, platform_id: str, status: str = "active") -> Path:
    path = root / platform_id
    path.mkdir(parents=True)
    path.joinpath("manifest.yaml").write_text(
        "\n".join(
            [
                f"platform_id: {platform_id}",
                f"name: {platform_id.title()} Platform",
                "domain: test-domain",
                "owners:",
                '  - "@tester"',
                f"status: {status}",
                "data_source_kind: static",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _write_schema(root: Path, platform_id: str) -> None:
    root.joinpath("schema.json").write_text(
        json.dumps(
            {
                "platform_id": platform_id,
                "version": 1,
                "classes": {"Customer": {"static_attrs": ["customer_no"], "operators": [], "actions": []}},
                "relations": {},
            }
        ),
        encoding="utf-8",
    )
