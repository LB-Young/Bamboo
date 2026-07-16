"""Validation helpers for BKN packages."""

from __future__ import annotations

from dataclasses import dataclass

from bamboo.bkn.models import BKNDefinition


@dataclass(slots=True)
class BKNValidationError(Exception):
    """Raised when a BKN package is structurally invalid."""

    message: str

    def __str__(self) -> str:
        return self.message


def validate_bkn_definition(definition: BKNDefinition) -> None:
    """Validate the minimum integrity constraints for a BKN package."""
    if not definition.name:
        raise BKNValidationError(f"{definition.source_path}: name is required")
    if definition.schema_version != 1:
        raise BKNValidationError(f"{definition.source_path}: unsupported schema_version {definition.schema_version}")
    if not definition.ontology.classes:
        raise BKNValidationError(f"{definition.source_path}: ontology classes are required")

    for entity in definition.entities.values():
        if not entity.id:
            raise BKNValidationError(f"{entity.source_path}: entity id is required")
        if not entity.entity_class:
            raise BKNValidationError(f"{entity.source_path}: entity class is required for {entity.id}")
        if entity.entity_class not in definition.ontology.classes:
            raise BKNValidationError(
                f"{entity.source_path}: entity {entity.id} references unknown class {entity.entity_class}"
            )

    relation_types = set(definition.ontology.relations)
    for relation in definition.relations:
        if relation.from_id not in definition.entities:
            raise BKNValidationError(
                f"{relation.source_path}: relation {relation.relation_type} references missing from entity "
                f"{relation.from_id}"
            )
        if relation.to_id not in definition.entities:
            raise BKNValidationError(
                f"{relation.source_path}: relation {relation.relation_type} references missing to entity "
                f"{relation.to_id}"
            )
        if relation_types and relation.relation_type not in relation_types:
            raise BKNValidationError(
                f"{relation.source_path}: relation {relation.relation_type} is not declared in ontology"
            )
