"""Tests for BKN update tools."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest

from bamboo.bkn.update import update_manifest, update_topology
from bamboo.bkn.validator import BKNValidationError
from bamboo.security.permission_policy import PermissionPolicy, PermissionRequest
from bamboo.tools.buildin.bkn_update_manifest import BKNUpdateManifestTool
from bamboo.tools.buildin.bkn_update_topology import BKNUpdateTopologyTool


@pytest.fixture(autouse=True)
def isolated_bkn_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("bamboo.bkn.update.get_user_bkn_dir", lambda: tmp_path / "bkn")


def test_update_manifest_rejects_paused_platform(tmp_path: Path) -> None:
    _platform(tmp_path / "bkn", status="paused")

    with pytest.raises(BKNValidationError, match="not writeable"):
        update_manifest(platform_id="billing", updates={"description": "new"}, bkn_root=tmp_path / "bkn")


def test_update_topology_requires_evidence(tmp_path: Path) -> None:
    _platform(tmp_path / "bkn")

    with pytest.raises(BKNValidationError, match="require evidence"):
        update_topology(platform_id="billing", nodes=[], edges=[], evidence=[], bkn_root=tmp_path / "bkn")


def test_update_topology_writes_graph_and_events(tmp_path: Path) -> None:
    root = _platform(tmp_path / "bkn")

    result = update_topology(
        platform_id="billing",
        nodes=[{"id": "customer:c001", "ontology_class": "Customer", "name": "Customer C001"}],
        edges=[],
        evidence=["manual:test"],
        bkn_root=tmp_path / "bkn",
    )

    assert result["nodes"] == 1
    assert (root / "graph.sqlite").is_file()
    assert "topology.updated" in (root / "events.jsonl").read_text(encoding="utf-8")


def test_bkn_update_tools_are_write_risk() -> None:
    policy = PermissionPolicy()
    result = policy.assess_risk(
        PermissionRequest(
            session_id="s",
            task_id="t",
            tool_call_id="c",
            tool_name="bkn_update_topology",
            arguments={},
            risk_level=BKNUpdateTopologyTool.risk_level,
        )
    )
    assert result.risk_level == "write"
    assert result.requires_confirmation is True
    assert BKNUpdateManifestTool.risk_level == "write"


def test_bkn_update_topology_tool_returns_validation_errors(tmp_path: Path) -> None:
    _platform(tmp_path / "bkn")
    tool = BKNUpdateTopologyTool()

    async def run_test() -> None:
        result = await tool.execute(platform_id="billing", evidence=[])
        assert not result.success
        assert result.error

    anyio.run(run_test)


def _platform(root: Path, *, status: str = "active") -> Path:
    platform_root = root / "platforms" / "billing"
    platform_root.mkdir(parents=True)
    platform_root.joinpath("manifest.yaml").write_text(
        "\n".join(
            [
                "platform_id: billing",
                "name: Billing",
                "domain: billing",
                "owners:",
                '  - "@tester"',
                f"status: {status}",
                "data_source_kind: static",
                "",
            ]
        ),
        encoding="utf-8",
    )
    platform_root.joinpath("schema.json").write_text(
        json.dumps({"platform_id": "billing", "version": 1, "classes": {"Customer": {}}, "relations": {}}),
        encoding="utf-8",
    )
    return platform_root
