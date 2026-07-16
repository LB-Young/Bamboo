"""Export BKN definitions as readable graph formats."""

from __future__ import annotations

import re
from collections import deque
from typing import Literal

from bamboo.bkn.models import BKNDefinition, BKNEntity, BKNRelation

BKNExportFormat = Literal["mermaid", "dot", "markdown"]


def export_bkn(
    definition: BKNDefinition,
    *,
    output_format: BKNExportFormat = "mermaid",
    node: str = "",
    depth: int = 1,
) -> str:
    """Export a full BKN or node-centered subgraph."""
    nodes, relations = select_bkn_subgraph(definition, node=node, depth=depth)
    if output_format == "mermaid":
        return render_mermaid(definition, nodes=nodes, relations=relations)
    if output_format == "dot":
        return render_dot(definition, nodes=nodes, relations=relations)
    if output_format == "markdown":
        return render_markdown(definition, nodes=nodes, relations=relations)
    raise ValueError(f"unsupported BKN export format: {output_format}")


def select_bkn_subgraph(
    definition: BKNDefinition,
    *,
    node: str = "",
    depth: int = 1,
) -> tuple[dict[str, BKNEntity], tuple[BKNRelation, ...]]:
    """Return entities and relations for a full graph or node neighborhood."""
    if not node:
        return dict(sorted(definition.entities.items())), tuple(sorted_relations(definition.relations))
    if node not in definition.entities:
        return {}, ()
    bounded_depth = max(0, int(depth))
    selected_ids = {node}
    selected_relations: list[BKNRelation] = []
    seen_relations: set[tuple[str, str, str]] = set()
    frontier: deque[tuple[str, int]] = deque([(node, 0)])
    while frontier:
        current, level = frontier.popleft()
        if level >= bounded_depth:
            continue
        for relation in sorted_relations(definition.relations):
            if relation.from_id != current and relation.to_id != current:
                continue
            relation_key = (relation.from_id, relation.relation_type, relation.to_id)
            if relation_key not in seen_relations:
                selected_relations.append(relation)
                seen_relations.add(relation_key)
            other = relation.to_id if relation.from_id == current else relation.from_id
            if other in definition.entities and other not in selected_ids:
                selected_ids.add(other)
                frontier.append((other, level + 1))
    return (
        {entity_id: definition.entities[entity_id] for entity_id in sorted(selected_ids) if entity_id in definition.entities},
        tuple(selected_relations),
    )


def render_mermaid(
    definition: BKNDefinition,
    *,
    nodes: dict[str, BKNEntity],
    relations: tuple[BKNRelation, ...],
) -> str:
    """Render a BKN graph as Mermaid flowchart."""
    if not nodes:
        return f"flowchart LR\n  empty[\"No BKN nodes found for {definition.name}\"]"
    lines = ["flowchart LR"]
    for entity_id, entity in nodes.items():
        lines.append(f"  {_node_ref(entity_id)}[\"{_escape_mermaid_label(entity.title)}\"]")
    for relation in relations:
        if relation.from_id in nodes and relation.to_id in nodes:
            lines.append(
                f"  {_node_ref(relation.from_id)} -->|{_escape_mermaid_label(relation.relation_type)}| "
                f"{_node_ref(relation.to_id)}"
            )
    return "\n".join(lines)


def render_dot(
    definition: BKNDefinition,
    *,
    nodes: dict[str, BKNEntity],
    relations: tuple[BKNRelation, ...],
) -> str:
    """Render a BKN graph as Graphviz DOT."""
    lines = [f'digraph "{_dot_escape(definition.name)}" {{']
    if not nodes:
        lines.append(f'  empty [label="No BKN nodes found for {_dot_escape(definition.name)}"];')
        lines.append("}")
        return "\n".join(lines)
    for entity_id, entity in nodes.items():
        lines.append(f'  "{_dot_escape(entity_id)}" [label="{_dot_escape(entity.title)}"];')
    for relation in relations:
        if relation.from_id in nodes and relation.to_id in nodes:
            lines.append(
                f'  "{_dot_escape(relation.from_id)}" -> "{_dot_escape(relation.to_id)}" '
                f'[label="{_dot_escape(relation.relation_type)}"];'
            )
    lines.append("}")
    return "\n".join(lines)


def render_markdown(
    definition: BKNDefinition,
    *,
    nodes: dict[str, BKNEntity],
    relations: tuple[BKNRelation, ...],
) -> str:
    """Render a BKN graph as Markdown."""
    lines = [f"# {definition.name}", ""]
    if not nodes:
        lines.append(f"No BKN nodes found for `{definition.name}`.")
        return "\n".join(lines)
    lines.append("## Nodes")
    for entity_id, entity in nodes.items():
        lines.append(f"- `{entity_id}` ({entity.entity_class}): {entity.title}")
    lines.extend(["", "## Relations"])
    visible_relations = [relation for relation in relations if relation.from_id in nodes and relation.to_id in nodes]
    if not visible_relations:
        lines.append("- No relations.")
        return "\n".join(lines)
    for relation in visible_relations:
        lines.append(f"- `{relation.from_id}` -[{relation.relation_type}]-> `{relation.to_id}`")
    return "\n".join(lines)


def sorted_relations(relations: tuple[BKNRelation, ...]) -> list[BKNRelation]:
    """Sort relations by stable graph identity."""
    return sorted(relations, key=lambda item: (item.from_id, item.relation_type, item.to_id))


def _node_ref(entity_id: str) -> str:
    value = re.sub(r"[^0-9A-Za-z_]", "_", entity_id)
    if value and value[0].isdigit():
        value = f"n_{value}"
    return value or "node"


def _escape_mermaid_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
