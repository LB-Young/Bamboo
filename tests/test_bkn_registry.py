"""Tests for BKN registry and store."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from bamboo.bkn.registry import BKNRegistry
from bamboo.bkn.store import BKNStore

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bkn" / "personal-media"


def test_bkn_registry_loads_enabled_network_and_writes_index(tmp_path: Path) -> None:
    bkn_dir = tmp_path / "bkn"
    storage_dir = tmp_path / "storage" / "bkn"
    shutil.copytree(FIXTURE_ROOT, bkn_dir / "personal-media")
    registry = BKNRegistry(bkn_dirs=[bkn_dir], store=BKNStore(root=storage_dir))

    definitions = registry.list()

    assert [definition.name for definition in definitions] == ["personal-media"]
    index_path = storage_dir / "indexes" / "personal-media.json"
    assert index_path.is_file()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["entities"]["content:agent-memory-design"]["class"] == "Content"


def test_bkn_registry_isolates_bad_packages(tmp_path: Path) -> None:
    bkn_dir = tmp_path / "bkn"
    storage_dir = tmp_path / "storage" / "bkn"
    shutil.copytree(FIXTURE_ROOT, bkn_dir / "personal-media")
    bad = bkn_dir / "bad"
    bad.mkdir(parents=True)
    (bad / "bkn.yaml").write_text("schema_version: 999\nname: bad\n", encoding="utf-8")
    registry = BKNRegistry(bkn_dirs=[bkn_dir], store=BKNStore(root=storage_dir))

    assert [definition.name for definition in registry.list()] == ["personal-media"]
    assert "bad" in next(iter(registry.errors()))


def test_bkn_registry_can_list_inactive_networks(tmp_path: Path) -> None:
    bkn_dir = tmp_path / "bkn"
    storage_dir = tmp_path / "storage" / "bkn"
    shutil.copytree(FIXTURE_ROOT, bkn_dir / "personal-media")
    entrypoint = bkn_dir / "personal-media" / "bkn.yaml"
    entrypoint.write_text(entrypoint.read_text(encoding="utf-8").replace("enabled: true", "enabled: false"), encoding="utf-8")
    registry = BKNRegistry(bkn_dirs=[bkn_dir], store=BKNStore(root=storage_dir))

    assert registry.list() == []
    assert [definition.name for definition in registry.list(include_inactive=True)] == ["personal-media"]
    assert not (storage_dir / "indexes" / "personal-media.json").exists()
