"""Tests for BKN HTTP/API attrs."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from bamboo.bkn.attrs_store import BknAttrsStore, HttpApiAdapter
from bamboo.bkn.models import BKNDefinition, BKNEntity, BknManifest, BKNOntology, BKNSource


def test_http_api_adapter_fetches_and_redacts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bamboo.bkn.attrs_store.is_url_allowed", lambda url: (True, "allowed"))
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"views": 10, "api_token": "secret"}))
    )
    adapter = HttpApiAdapter(base_url="https://api.example.com/v1", client=client)

    payload = adapter.fetch(
        BKNSource("stats", "api_endpoint", {"path": "/content/{id}"}),
        BKNEntity("content:one", "Content", {"slug": "one"}),
    )

    assert payload == {"views": 10, "api_token": "[redacted]"}


def test_bkn_attrs_store_marks_blocked_http_url_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("bamboo.bkn.attrs_store.is_url_allowed", lambda url: (False, "blocked test url"))
    definition = BKNDefinition(
        name="demo",
        root=tmp_path,
        ontology=BKNOntology(classes={"Content": {}}, relations={}),
        entities={"content:one": BKNEntity("content:one", "Content", {"source": "stats"})},
        sources={"stats": BKNSource("stats", "api_endpoint", {"base_url": "https://api.example.com", "path": "/x/{id}"})},
    )

    fetch = BknAttrsStore(definition).get_attrs(definition.entities["content:one"])

    assert fetch.warnings == ("blocked test url",)
    assert fetch.values["source"] == "stats"


def test_manifest_api_endpoint_fetches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("bamboo.bkn.attrs_store.is_url_allowed", lambda url: (True, "allowed"))
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "active"})))
    manifest = BknManifest(
        platform_id="billing",
        name="Billing",
        domain="billing",
        owners=("@tester",),
        status="active",
        data_source_kind="api_endpoint",
        base_url="https://api.example.com/v1",
    )
    definition = BKNDefinition(
        name="billing",
        platform_id="billing",
        root=tmp_path,
        manifest=manifest,
        ontology=BKNOntology(classes={"Customer": {}}, relations={}),
        entities={"customer:c001": BKNEntity("customer:c001", "Customer", {"endpoint": "/customers/{id}"})},
    )

    fetch = BknAttrsStore(definition, http_client=client).get_attrs(definition.entities["customer:c001"])

    assert fetch.values["status"] == "active"
