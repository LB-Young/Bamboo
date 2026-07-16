"""Load BKN package files from disk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bamboo.bkn.attrs_store import BknAttrsStore
from bamboo.bkn.graph import BknGraph
from bamboo.bkn.manifest_io import read_manifest, read_schema, validate_manifest_schema_match
from bamboo.bkn.models import (
    BKNAction,
    BKNDefinition,
    BKNEntity,
    BKNOntology,
    BKNOperator,
    BKNRelation,
    BknSnapshot,
    BKNSource,
)
from bamboo.bkn.operators import evaluate_expression_operator
from bamboo.bkn.validator import BKNValidationError, validate_bkn_definition


def load_bkn_definition(root: Path) -> BKNDefinition:
    """Load and validate one BKN package rooted at a directory containing bkn.yaml."""
    root = root.expanduser().resolve()
    if (root / "manifest.yaml").is_file():
        return load_platform_bkn_definition(root)
    entry_path = root / "bkn.yaml"
    document = _read_yaml_mapping(entry_path)
    entrypoints = _mapping(document.get("entrypoints"))

    ontology_path = root / str(entrypoints.get("ontology", "schema/ontology.yaml"))
    entities_path = root / str(entrypoints.get("entities", "graph/entities.yaml"))
    relations_path = root / str(entrypoints.get("relations", "graph/relations.yaml"))

    ontology = _load_ontology(ontology_path)
    entities = _load_entities(entities_path)
    relations = _load_relations(relations_path)
    sources = _load_sources(root / "sources")
    operators = _load_named_specs(root / "operators", "operators", BKNOperator)
    actions = _load_named_specs(root / "actions", "actions", BKNAction)
    retrieval = _mapping(document.get("retrieval"))

    definition = BKNDefinition(
        name=str(document.get("name", root.name)),
        root=root,
        platform_id="",
        description=str(document.get("description", "")),
        enabled=bool(document.get("enabled", True)),
        schema_version=int(document.get("schema_version", 1)),
        ontology=ontology,
        entities=entities,
        relations=tuple(relations),
        sources=sources,
        operators=operators,
        actions=actions,
        default_limit=int(retrieval.get("default_limit", 5)),
        max_hops=int(retrieval.get("max_hops", 2)),
        source_path=str(entry_path),
    )
    validate_bkn_definition(definition)
    return definition


def load_platform_bkn_definition(root: Path) -> BKNDefinition:
    """Load a platform BKN package rooted at platforms/<platform_id>."""
    root = root.expanduser().resolve()
    manifest_path = root / "manifest.yaml"
    schema_path = root / "schema.json"
    manifest = read_manifest(manifest_path)
    schema = read_schema(schema_path)
    validate_manifest_schema_match(manifest, schema, schema_path=schema_path)
    classes = _mapping(schema.get("classes"))
    relations = _mapping(schema.get("relations"))
    ontology = BKNOntology(classes=classes, relations=relations)
    graph = BknGraph(root=root, platform_id=manifest.platform_id)
    entities = {
        node.id.value: BKNEntity(
            id=node.id.value,
            entity_class=node.ontology_class,
            properties={
                "name": node.name,
                "aliases": list(node.aliases),
                "description": node.description,
                **dict(node.static_attrs),
            },
            source_path=str(graph.db_path),
        )
        for node in graph.find_nodes()
    }
    bkn_relations = tuple(
        BKNRelation(
            from_id=edge.src.value,
            relation_type=edge.relation,
            to_id=edge.dst.value,
            properties={"weight": edge.weight},
            source_path=str(graph.db_path),
        )
        for edge in graph.list_edges()
    )
    actions = {**_actions_from_schema(schema, root), **_load_named_specs(root / "actions", "actions", BKNAction)}
    operators = _operators_from_schema(schema, root)
    definition = BKNDefinition(
        name=manifest.platform_id,
        root=root,
        platform_id=manifest.platform_id,
        description=manifest.description,
        enabled=manifest.is_active(),
        schema_version=int(schema.get("version", 1)),
        manifest=manifest,
        ontology=ontology,
        entities=entities,
        relations=bkn_relations,
        sources={},
        operators=operators,
        actions=actions,
        default_limit=5,
        max_hops=2,
        source_path=str(manifest_path),
    )
    validate_bkn_definition(definition)
    return definition


def _load_ontology(path: Path) -> BKNOntology:
    document = _read_yaml_mapping(path)
    return BKNOntology(classes=_mapping(document.get("classes")), relations=_mapping(document.get("relations")))


def _load_entities(path: Path) -> dict[str, BKNEntity]:
    document = _read_yaml_mapping(path)
    entities: dict[str, BKNEntity] = {}
    for item in _sequence(document.get("entities")):
        raw = _mapping(item)
        entity_id = str(raw.get("id", ""))
        entity_class = str(raw.get("class", raw.get("entity_class", "")))
        properties = {key: value for key, value in raw.items() if key not in {"id", "class", "entity_class"}}
        entities[entity_id] = BKNEntity(
            id=entity_id,
            entity_class=entity_class,
            properties=properties,
            source_path=str(path),
        )
    return entities


def _load_relations(path: Path) -> list[BKNRelation]:
    document = _read_yaml_mapping(path)
    relations: list[BKNRelation] = []
    for item in _sequence(document.get("relations")):
        raw = _mapping(item)
        relation_type = str(raw.get("type", raw.get("relation", "")))
        properties = {key: value for key, value in raw.items() if key not in {"from", "to", "type", "relation"}}
        relations.append(
            BKNRelation(
                from_id=str(raw.get("from", "")),
                relation_type=relation_type,
                to_id=str(raw.get("to", "")),
                properties=properties,
                source_path=str(path),
            )
        )
    return relations


def _load_sources(root: Path) -> dict[str, BKNSource]:
    if not root.exists():
        return {}
    sources: dict[str, BKNSource] = {}
    for path in sorted(root.glob("*.yaml")):
        document = _read_yaml_mapping(path)
        for name, raw_value in _mapping(document.get("sources")).items():
            raw = _mapping(raw_value)
            source_type = str(raw.get("type", "static"))
            config = {key: value for key, value in raw.items() if key != "type"}
            sources[str(name)] = BKNSource(str(name), source_type, config, str(path))
    return sources


def _load_named_specs(root: Path, key: str, model_type: type[BKNOperator] | type[BKNAction]) -> dict[str, Any]:
    if not root.exists():
        return {}
    specs: dict[str, Any] = {}
    for path in sorted(root.glob("*.yaml")):
        document = _read_yaml_mapping(path)
        for name, raw_value in _mapping(document.get(key)).items():
            raw = _mapping(raw_value)
            specs[str(name)] = model_type(
                name=str(name),
                description=str(raw.get("description", "")),
                config={item_key: item_value for item_key, item_value in raw.items() if item_key != "description"},
                source_path=str(path),
            )
    return specs


def _actions_from_schema(schema: dict[str, Any], root: Path) -> dict[str, BKNAction]:
    registry = _mapping(schema.get("action_registry"))
    actions: dict[str, BKNAction] = {}
    for name, value in registry.items():
        raw = _mapping(value)
        actions[str(name)] = BKNAction(
            name=str(name),
            description=str(raw.get("description", "")),
            config={key: item for key, item in raw.items() if key != "description"},
            source_path=str(root / "schema.json"),
        )
    for class_spec in _mapping(schema.get("classes")).values():
        for name in _sequence(_mapping(class_spec).get("actions")):
            if isinstance(name, str) and name not in actions:
                actions[name] = BKNAction(name=name, source_path=str(root / "schema.json"))
    return actions


def _operators_from_schema(schema: dict[str, Any], root: Path) -> dict[str, BKNOperator]:
    registry = _mapping(schema.get("operator_registry"))
    operators: dict[str, BKNOperator] = {}
    for name, value in registry.items():
        operators[str(name)] = BKNOperator(
            name=str(name),
            description=str(value) if isinstance(value, str) else str(_mapping(value).get("description", "")),
            config={"entry": value} if isinstance(value, str) else _mapping(value),
            source_path=str(root / "schema.json"),
        )
    for class_spec in _mapping(schema.get("classes")).values():
        for name in _sequence(_mapping(class_spec).get("operators")):
            if isinstance(name, str) and name not in operators:
                operators[name] = BKNOperator(name=name, source_path=str(root / "schema.json"))
    return operators


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


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class BknLoader:
    """Context Loader: focus entity ids -> BknSnapshot."""

    def __init__(self, definition: BKNDefinition, attrs_store: BknAttrsStore | None = None) -> None:
        self.definition = definition
        self.attrs_store = attrs_store or BknAttrsStore(definition)

    def load(
        self,
        *,
        focus: tuple[str, ...],
        depth: int = 1,
        include_attrs: bool = True,
        run_operators: tuple[str, ...] = (),
        available_actions: tuple[str, ...] = (),
        max_nodes: int = 80,
    ) -> BknSnapshot:
        """Load a bounded BKN snapshot for focused entities."""
        focus_set = {node_id for node_id in focus if node_id in self.definition.entities}
        related_relations = self._expand_relations(focus_set, depth=depth)
        node_ids = self._node_ids(focus_set, related_relations)[:max_nodes]
        skeleton = tuple(
            f"({relation.from_id})-[{relation.relation_type}]->({relation.to_id})"
            for relation in related_relations
            if relation.from_id in node_ids and relation.to_id in node_ids
        )
        attrs: dict[str, dict[str, Any]] = {}
        attrs_unavailable: list[str] = []
        if include_attrs:
            for node_id in node_ids:
                entity = self.definition.entities[node_id]
                fetch = self.attrs_store.get_attrs(entity)
                attrs[node_id] = dict(fetch.values)
                if fetch.warnings:
                    attrs_unavailable.append(node_id)
        operator_outputs = self._operator_outputs(node_ids, attrs=attrs, run_operators=run_operators)
        actions = self._available_actions(node_ids, requested=available_actions)
        return BknSnapshot(
            platform_id=self.definition.platform_id or self.definition.name,
            manifest_status=self.definition.manifest.status if self.definition.manifest else "active",
            skeleton=skeleton,
            static_attrs=attrs,
            operator_outputs=operator_outputs,
            available_actions=actions,
            open_hypotheses=(),
            attrs_unavailable=tuple(attrs_unavailable),
        )

    def _expand_relations(self, focus: set[str], *, depth: int) -> list[BKNRelation]:
        if depth <= 0:
            return []
        seen_nodes = set(focus)
        frontier = set(focus)
        relations: list[BKNRelation] = []
        seen_relations: set[tuple[str, str, str]] = set()
        for _ in range(depth):
            next_frontier: set[str] = set()
            for relation in self.definition.relations:
                if relation.from_id not in frontier and relation.to_id not in frontier:
                    continue
                key = (relation.from_id, relation.relation_type, relation.to_id)
                if key not in seen_relations:
                    relations.append(relation)
                    seen_relations.add(key)
                other = relation.to_id if relation.from_id in frontier else relation.from_id
                if other not in seen_nodes:
                    seen_nodes.add(other)
                    next_frontier.add(other)
            frontier = next_frontier
            if not frontier:
                break
        return relations

    @staticmethod
    def _node_ids(focus: set[str], relations: list[BKNRelation]) -> list[str]:
        ordered: list[str] = []
        for node_id in sorted(focus):
            if node_id not in ordered:
                ordered.append(node_id)
        for relation in relations:
            for node_id in (relation.from_id, relation.to_id):
                if node_id not in ordered:
                    ordered.append(node_id)
        return ordered

    def _operator_outputs(
        self,
        node_ids: list[str],
        *,
        attrs: dict[str, dict[str, Any]],
        run_operators: tuple[str, ...],
    ) -> dict[str, dict[str, Any]]:
        outputs: dict[str, dict[str, Any]] = {}
        requested = set(run_operators)
        for node_id in node_ids:
            entity = self.definition.entities[node_id]
            class_spec = _mapping(self.definition.ontology.classes.get(entity.entity_class))
            operator_names = [name for name in _sequence(class_spec.get("operators")) if isinstance(name, str)]
            if requested:
                operator_names = [name for name in operator_names if name in requested]
            node_outputs: dict[str, Any] = {}
            for name in operator_names:
                if name not in self.definition.operators:
                    continue
                operator = self.definition.operators[name]
                if operator.config.get("type") == "expression" and operator.config.get("expression"):
                    try:
                        node_outputs[name] = evaluate_expression_operator(str(operator.config["expression"]), attrs.get(node_id, {}))
                    except (ValueError, TypeError, ZeroDivisionError) as exc:
                        node_outputs[name] = f"error: {exc}"
                else:
                    node_outputs[name] = operator.description
            if node_outputs:
                outputs[node_id] = node_outputs
        return outputs

    def _available_actions(self, node_ids: list[str], *, requested: tuple[str, ...]) -> tuple[BKNAction, ...]:
        requested_set = set(requested)
        allowlist = set(self.definition.manifest.action_allowlist) if self.definition.manifest else None
        actions: dict[str, BKNAction] = {}
        for node_id in node_ids:
            entity = self.definition.entities[node_id]
            class_spec = _mapping(self.definition.ontology.classes.get(entity.entity_class))
            for name in _sequence(class_spec.get("actions")):
                if not isinstance(name, str) or name not in self.definition.actions:
                    continue
                if requested_set and name not in requested_set:
                    continue
                if allowlist is not None and name not in allowlist:
                    continue
                actions[name] = self.definition.actions[name]
        return tuple(actions[name] for name in sorted(actions))
