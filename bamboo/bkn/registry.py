"""Registry for user BKN packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bamboo.bkn.loader import load_bkn_definition
from bamboo.bkn.models import BKNDefinition, BKNRetrievalMatch
from bamboo.bkn.store import BKNStore
from bamboo.bkn.validator import BKNValidationError
from bamboo.userspace.userspace import get_user_bkn_dir


class BKNRegistry:
    """Scan, validate, index, and search BKN packages."""

    def __init__(self, *, bkn_dirs: list[Path] | None = None, store: BKNStore | None = None) -> None:
        self.bkn_dirs = bkn_dirs or [get_user_bkn_dir()]
        self.store = store or BKNStore()
        self._definitions: dict[str, BKNDefinition] = {}
        self._errors: dict[str, str] = {}
        self._loaded = False

    def refresh(self) -> None:
        """Reload all BKN packages from configured directories."""
        definitions: dict[str, BKNDefinition] = {}
        errors: dict[str, str] = {}
        self.store.ensure()
        for package_root in self._package_roots():
            try:
                definition = load_bkn_definition(package_root)
            except BKNValidationError as exc:
                errors[str(package_root)] = str(exc)
                self.store.append_audit({"action": "load_failed", "root": str(package_root), "error": str(exc)})
                continue
            definitions[definition.name] = definition
            if definition.enabled:
                self.store.write_index(definition)
        self._definitions = definitions
        self._errors = errors
        self._loaded = True
        self.store.write_state(
            {
                "networks": sorted(definitions),
                "active_networks": sorted(name for name, definition in definitions.items() if definition.enabled),
                "errors": errors,
            }
        )

    def list(self, *, include_inactive: bool = False) -> list[BKNDefinition]:
        """Return loaded definitions."""
        self._ensure_loaded()
        if include_inactive:
            return sorted(self._definitions.values(), key=lambda item: item.name)
        return sorted((item for item in self._definitions.values() if item.enabled), key=lambda item: item.name)

    def get(self, name: str) -> BKNDefinition | None:
        """Return one loaded definition by name."""
        self._ensure_loaded()
        return self._definitions.get(name)

    def errors(self) -> dict[str, str]:
        """Return package load errors from the last refresh."""
        self._ensure_loaded()
        return dict(self._errors)

    def search(
        self,
        query: str,
        *,
        network: str = "auto",
        limit: int = 5,
        max_hops: int = 2,
        include_dynamic_data: bool = True,
        include_actions: bool = True,
    ) -> list[BKNRetrievalMatch]:
        """Search loaded BKN packages."""
        self._ensure_loaded()
        from bamboo.bkn.retrieval import retrieve_bkn

        return retrieve_bkn(
            query=query,
            definitions=self.list(),
            network=network,
            limit=limit,
            max_hops=max_hops,
            include_dynamic_data=include_dynamic_data,
            include_actions=include_actions,
        )

    def summary(self) -> dict[str, Any]:
        """Return a compact registry summary."""
        self._ensure_loaded()
        return {
            "networks": sorted(self._definitions),
            "active_networks": sorted(name for name, definition in self._definitions.items() if definition.enabled),
            "errors": dict(self._errors),
        }

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.refresh()

    def _package_roots(self) -> list[Path]:
        roots: list[Path] = []
        for bkn_dir in self.bkn_dirs:
            if not bkn_dir.exists():
                continue
            if (bkn_dir / "bkn.yaml").is_file():
                roots.append(bkn_dir)
            roots.extend(path.parent for path in sorted(bkn_dir.glob("*/bkn.yaml")))
            roots.extend(path.parent for path in sorted(bkn_dir.glob("platforms/*/manifest.yaml")))
        return roots


def create_bkn_registry(*, bkn_dirs: list[Path] | None = None, store: BKNStore | None = None) -> BKNRegistry:
    """Create a BKN registry."""
    return BKNRegistry(bkn_dirs=bkn_dirs, store=store)
