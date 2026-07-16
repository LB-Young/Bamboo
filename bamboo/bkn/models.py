"""Data models for Bamboo Knowledge Network packages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class BKNOntology:
    """Ontology classes and relation definitions for one BKN package."""

    classes: dict[str, dict[str, Any]] = field(default_factory=dict)
    relations: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BKNEntity:
    """A lightweight business object declared in a BKN graph file."""

    id: str
    entity_class: str
    properties: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""

    @property
    def title(self) -> str:
        value = self.properties.get("title") or self.properties.get("name") or self.id
        return str(value)

    @property
    def summary(self) -> str:
        description = self.properties.get("description") or self.properties.get("summary") or ""
        if description:
            return str(description)
        return f"{self.entity_class} {self.title}"


@dataclass(frozen=True, slots=True)
class BKNRelation:
    """A directed relation between two BKN entities."""

    from_id: str
    relation_type: str
    to_id: str
    properties: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""


@dataclass(frozen=True, slots=True)
class BKNSource:
    """A read-only data source declaration."""

    name: str
    source_type: str
    config: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""


@dataclass(frozen=True, slots=True)
class BKNOperator:
    """Operator metadata attached to BKN classes or entities."""

    name: str
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""


@dataclass(frozen=True, slots=True)
class BKNAction:
    """Action metadata attached to BKN classes or entities."""

    name: str
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""


@dataclass(frozen=True, slots=True)
class BknNodeId:
    """Stable node id used by the SQLite skeleton graph."""

    value: str


@dataclass(frozen=True, slots=True)
class BknEdgeId:
    """Stable edge id used by the SQLite skeleton graph."""

    value: str


class NodeKind(StrEnum):
    """Supported skeleton node kinds."""

    ENTITY = "entity"
    CONCEPT = "concept"
    EVENT = "event"
    METRIC = "metric"
    HYPOTHESIS = "hypothesis"
    SOURCE = "source"


@dataclass(frozen=True, slots=True)
class BknDataSourceRef:
    """Pointer from a skeleton node to a data source."""

    kind: Literal["static", "file", "json", "csv", "sqlite", "api_endpoint"] = "static"
    location: str = ""
    field_mapping: Mapping[str, str] = field(default_factory=dict)
    cacheable: bool = False
    cache_key: str | None = None


@dataclass(frozen=True, slots=True)
class BknNode:
    """SQLite skeleton node: stable metadata only, no hot data payload."""

    id: BknNodeId
    platform_id: str
    kind: NodeKind
    ontology_class: str
    name: str
    aliases: tuple[str, ...] = ()
    description: str = ""
    static_attrs: Mapping[str, Any] = field(default_factory=dict)
    data_source: BknDataSourceRef | None = None
    evidence_ids: tuple[BknNodeId, ...] = ()
    confidence: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 1


@dataclass(frozen=True, slots=True)
class BknEdge:
    """SQLite skeleton edge: topology and evidence only."""

    id: BknEdgeId
    src: BknNodeId
    dst: BknNodeId
    relation: str
    weight: float = 1.0
    evidence_ids: tuple[BknNodeId, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class BknManifest:
    """Platform-level BKN manifest."""

    platform_id: str
    name: str
    domain: str
    owners: tuple[str, ...]
    created_at: datetime | None = None
    updated_at: datetime | None = None
    version: int = 1
    status: Literal["draft", "active", "paused", "deprecated"] = "draft"
    description: str = ""
    data_source_kind: Literal["static", "file", "json", "csv", "sqlite", "api_endpoint"] = "static"
    base_url: str = ""
    auth_ref: str = ""
    cacheable: bool = False
    cache_strategy: Literal["etag", "last_modified", "ttl"] = "ttl"
    cache_ttl_seconds: int = 300
    operator_allowlist: tuple[str, ...] = ()
    action_allowlist: tuple[str, ...] = ()
    cross_platform_edges_allowed: bool = False
    source_path: str = ""

    def is_writeable(self) -> bool:
        return self.status in {"draft", "active"}

    def is_active(self) -> bool:
        return self.status in {"draft", "active"}


@dataclass(frozen=True, slots=True)
class BknScope:
    """BKN namespace rooted at one platform directory."""

    platform_id: str
    root_dir: Path
    project_hash: str = ""
    env: Literal["dev", "staging", "prod"] = "prod"

    @property
    def root(self) -> Path:
        return self.root_dir / "platforms" / self.platform_id if self.root_dir.name != self.platform_id else self.root_dir


@dataclass(frozen=True, slots=True)
class BknAttrFetch:
    """Dynamic attributes fetched for one node."""

    node_id: str
    values: Mapping[str, Any] = field(default_factory=dict)
    source: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    cache_hit: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BknSnapshot:
    """Model-facing context assembled from graph, attrs, operators, and actions."""

    platform_id: str
    manifest_status: str
    skeleton: tuple[str, ...] = ()
    static_attrs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    operator_outputs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    available_actions: tuple[BKNAction, ...] = ()
    open_hypotheses: tuple[str, ...] = ()
    attrs_unavailable: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BKNDefinition:
    """One loaded BKN package."""

    name: str
    root: Path
    platform_id: str = ""
    description: str = ""
    enabled: bool = True
    schema_version: int = 1
    manifest: BknManifest | None = None
    ontology: BKNOntology = field(default_factory=BKNOntology)
    entities: dict[str, BKNEntity] = field(default_factory=dict)
    relations: tuple[BKNRelation, ...] = ()
    sources: dict[str, BKNSource] = field(default_factory=dict)
    operators: dict[str, BKNOperator] = field(default_factory=dict)
    actions: dict[str, BKNAction] = field(default_factory=dict)
    default_limit: int = 5
    max_hops: int = 2
    source_path: str = ""


@dataclass(frozen=True, slots=True)
class BKNRetrievalMatch:
    """One rendered BKN retrieval match."""

    network: str
    entity_id: str
    entity_class: str
    score: int
    summary: str
    relations: tuple[BKNRelation, ...] = ()
    dynamic_data: dict[str, Any] = field(default_factory=dict)
    operators: tuple[BKNOperator, ...] = ()
    actions: tuple[BKNAction, ...] = ()
    source_path: str = ""
