"""BKN retrieval and result rendering."""

from __future__ import annotations

from html import escape
from typing import Any

from bamboo.bkn.models import BKNAction, BKNDefinition, BKNOperator, BKNRelation, BKNRetrievalMatch
from bamboo.bkn.source_readers import load_dynamic_data


def retrieve_bkn(
    *,
    query: str,
    definitions: list[BKNDefinition],
    network: str = "auto",
    limit: int = 5,
    max_hops: int = 2,
    include_dynamic_data: bool = True,
    include_actions: bool = True,
) -> list[BKNRetrievalMatch]:
    """Search BKN definitions and return ranked matches."""
    selected = [definition for definition in definitions if _network_matches(definition, network)]
    matches: list[BKNRetrievalMatch] = []
    for definition in selected:
        for entity_id, entity in definition.entities.items():
            score = _score_entity(query, entity_id, entity.entity_class, entity.properties)
            if score <= 0:
                continue
            relations = tuple(_expand_relations(definition, entity_id, depth=max_hops))
            dynamic_data = (
                load_dynamic_data(root=definition.root, entity=entity, sources=definition.sources)
                if include_dynamic_data
                else dict(entity.properties)
            )
            matches.append(
                BKNRetrievalMatch(
                    network=definition.name,
                    entity_id=entity_id,
                    entity_class=entity.entity_class,
                    score=score,
                    summary=entity.summary,
                    relations=relations,
                    dynamic_data=dynamic_data,
                    operators=_operators_for_entity(definition, entity.entity_class),
                    actions=_actions_for_entity(definition, entity.entity_class) if include_actions else (),
                    source_path=entity.source_path,
                )
            )
    return sorted(matches, key=lambda item: (-item.score, item.network, item.entity_id))[:limit]


def render_bkn_results(*, query: str, network: str, matches: list[BKNRetrievalMatch]) -> str:
    """Render matches in a compact XML-like format for the model."""
    if not matches:
        return f'<bkn_results query="{escape(query)}" network="{escape(network)}" count="0" />'
    chunks = [f'<bkn_results query="{escape(query)}" network="{escape(network)}" count="{len(matches)}">']
    for index, match in enumerate(matches, start=1):
        chunks.append(
            f'  <result index="{index}" network="{escape(match.network)}" '
            f'entity_id="{escape(match.entity_id)}" class="{escape(match.entity_class)}" score="{match.score}">'
        )
        chunks.append(f"    <summary>{escape(match.summary)}</summary>")
        if match.relations:
            chunks.append("    <relations>")
            for relation in match.relations:
                chunks.append(
                    "      - "
                    f"{escape(relation.from_id)} -[{escape(relation.relation_type)}]-&gt; {escape(relation.to_id)}"
                )
            chunks.append("    </relations>")
        if match.dynamic_data:
            chunks.append("    <dynamic_data>")
            for key, value in sorted(match.dynamic_data.items()):
                chunks.append(f"      {escape(str(key))}: {escape(_compact_value(value))}")
            chunks.append("    </dynamic_data>")
        if match.operators:
            chunks.append("    <operators>")
            for operator in match.operators:
                chunks.append(f"      - {escape(operator.name)}: {escape(operator.description)}")
            chunks.append("    </operators>")
        if match.actions:
            chunks.append("    <actions>")
            for action in match.actions:
                chunks.append(f"      - {escape(action.name)}: {escape(action.description)}")
            chunks.append("    </actions>")
        chunks.append("  </result>")
    chunks.append("</bkn_results>")
    return "\n".join(chunks)


def _network_matches(definition: BKNDefinition, network: str) -> bool:
    return network == "auto" or not network or definition.name == network


def _score_entity(query: str, entity_id: str, entity_class: str, properties: dict[str, Any]) -> int:
    normalized_query = query.lower().strip()
    if not normalized_query:
        return 0
    haystack = " ".join([entity_id, entity_class, *(str(value) for value in properties.values())]).lower()
    score = 0
    if normalized_query == entity_id.lower():
        score += 100
    if normalized_query in haystack:
        score += 20
    for token in normalized_query.split():
        if token and token in haystack:
            score += 5
    return score


def _expand_relations(definition: BKNDefinition, entity_id: str, *, depth: int) -> list[BKNRelation]:
    if depth <= 0:
        return []
    seen_nodes = {entity_id}
    frontier = {entity_id}
    relations: list[BKNRelation] = []
    seen_relations: set[tuple[str, str, str]] = set()
    for _ in range(depth):
        next_frontier: set[str] = set()
        for relation in definition.relations:
            if relation.from_id not in frontier and relation.to_id not in frontier:
                continue
            relation_key = (relation.from_id, relation.relation_type, relation.to_id)
            if relation_key not in seen_relations:
                relations.append(relation)
                seen_relations.add(relation_key)
            other = relation.to_id if relation.from_id in frontier else relation.from_id
            if other not in seen_nodes:
                seen_nodes.add(other)
                next_frontier.add(other)
        frontier = next_frontier
        if not frontier:
            break
    return relations


def _operators_for_entity(definition: BKNDefinition, entity_class: str) -> tuple[BKNOperator, ...]:
    class_spec = definition.ontology.classes.get(entity_class, {})
    names = class_spec.get("operators", []) if isinstance(class_spec, dict) else []
    return tuple(definition.operators[name] for name in names if isinstance(name, str) and name in definition.operators)


def _actions_for_entity(definition: BKNDefinition, entity_class: str) -> tuple[BKNAction, ...]:
    class_spec = definition.ontology.classes.get(entity_class, {})
    names = class_spec.get("actions", []) if isinstance(class_spec, dict) else []
    return tuple(definition.actions[name] for name in names if isinstance(name, str) and name in definition.actions)


def _compact_value(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 500 else text[:497] + "..."
