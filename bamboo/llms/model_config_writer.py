"""Write discovered local models into Bamboo's models.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from bamboo.llms.local_discovery import LocalModelInfo


@dataclass(frozen=True, slots=True)
class ModelConfigWriteResult:
    """Result of writing discovered models to models.yaml."""

    path: Path
    backup_path: Path | None
    added: tuple[str, ...]
    skipped: tuple[str, ...]
    default_model: str


class ModelConfigWriter:
    """Safely merge discovered local model registrations into models.yaml."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write_discovered(
        self,
        models: list[LocalModelInfo] | tuple[LocalModelInfo, ...],
        *,
        set_default: bool = False,
        replace: bool = False,
    ) -> ModelConfigWriteResult:
        """Write models after creating a timestamped backup when the file exists."""
        document = self._load_document()
        raw_models = document.setdefault("models", {})
        if not isinstance(raw_models, dict):
            raise ValueError("models.yaml field 'models' must be a mapping")

        added: list[str] = []
        skipped: list[str] = []
        for model in models:
            name = unique_registration_name(model.registration_name, raw_models.keys())
            if model.registration_name in raw_models and not replace:
                skipped.append(model.registration_name)
                continue
            target_name = model.registration_name if replace else name
            raw_models[target_name] = model_to_config(model)
            added.append(target_name)

        if set_default and added:
            document["default_model"] = added[0]
        elif not document.get("default_model") and added:
            document["default_model"] = added[0]

        backup_path = self._backup_existing()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return ModelConfigWriteResult(
            path=self.path,
            backup_path=backup_path,
            added=tuple(added),
            skipped=tuple(skipped),
            default_model=str(document.get("default_model", "")),
        )

    def _load_document(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"default_model": "", "models": {}}
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        if raw is None:
            return {"default_model": "", "models": {}}
        if not isinstance(raw, dict):
            raise ValueError("models.yaml must contain a mapping")
        if "models" not in raw:
            raw["models"] = {}
        return raw

    def _backup_existing(self) -> Path | None:
        if not self.path.exists():
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = self.path.with_suffix(f".yaml.bak-{stamp}")
        backup_path.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")
        return backup_path


def model_to_config(model: LocalModelInfo) -> dict[str, Any]:
    """Convert a discovered local model to a Bamboo model registration."""
    return {
        "provider": model.provider,
        "model": model.model,
        "model_type": "text",
        "prompt_profile": model.provider,
        "api_key": "",
        "base_url": model.base_url,
        "timeout": 120,
        "temperature": 0.2,
        "context_window": 32768,
        "max_tokens": 4096,
        "capabilities": {
            "tool_calling": False,
            "json_schema": False,
            "vision": False,
            "max_parallel_tools": 1,
        },
    }


def render_models_yaml_snippet(models: list[LocalModelInfo] | tuple[LocalModelInfo, ...]) -> str:
    """Render a copyable models.yaml snippet for discovered local models."""
    document = {"models": {model.registration_name: model_to_config(model) for model in models}}
    return yaml.safe_dump(document, allow_unicode=True, sort_keys=False).rstrip()


def unique_registration_name(base_name: str, existing_names: Any) -> str:
    """Return a non-conflicting model registration name."""
    existing = set(str(name) for name in existing_names)
    if base_name not in existing:
        return base_name
    index = 2
    while f"{base_name}-{index}" in existing:
        index += 1
    return f"{base_name}-{index}"
