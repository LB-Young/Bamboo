"""Plugin manifest loading and validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from bamboo.plugins.models import PluginComponent, PluginMCPComponent, PluginManifest

MANIFEST_FILENAMES = ("bamboo-plugin.yaml", "bamboo-plugin.yml")
NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")


def load_plugin_manifest(plugin_dir: Path) -> PluginManifest:
    """Load and validate a plugin manifest from a plugin directory."""
    root = plugin_dir.expanduser().resolve()
    manifest_path = _find_manifest(root)
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("plugin manifest must be a mapping")
    name = _required_string(raw, "name")
    if not NAME_RE.match(name):
        raise ValueError("plugin name must use letters, numbers, dots, underscores or dashes")
    version = _required_string(raw, "version")
    manifest = PluginManifest(
        name=name,
        version=version,
        description=str(raw.get("description") or "").strip(),
        publisher=str(raw.get("publisher") or "").strip(),
        skills=_components(raw.get("skills", []), "skills", "skill"),
        commands=_components(raw.get("commands", []), "commands", "command"),
        workflows=_components(raw.get("workflows", []), "workflows", "workflow"),
        mcp=_mcp_component(raw.get("mcp")),
        permissions=_string_tuple(raw.get("permissions", []), "permissions"),
        compatibility=_mapping(raw.get("compatibility", {}), "compatibility"),
    )
    if not (manifest.skills or manifest.commands or manifest.workflows or manifest.mcp):
        raise ValueError("plugin must declare at least one component")
    _validate_paths(root, manifest)
    return manifest


def _find_manifest(root: Path) -> Path:
    if not root.is_dir():
        raise FileNotFoundError(f"plugin directory not found: {root}")
    for filename in MANIFEST_FILENAMES:
        path = root / filename
        if path.is_file():
            return path
    raise FileNotFoundError(f"plugin manifest not found in {root}")


def _required_string(raw: dict[str, Any], field_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"plugin manifest requires non-empty {field_name}")
    return value.strip()


def _components(value: Any, field_name: str, component_type: str) -> tuple[PluginComponent, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    components: list[PluginComponent] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if isinstance(item, str):
            path = item.strip()
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            path = item["path"].strip()
        else:
            raise ValueError(f"{field_name}[{index}] must be a path string or mapping with path")
        if not path:
            raise ValueError(f"{field_name}[{index}].path must not be empty")
        if path in seen:
            raise ValueError(f"duplicate plugin component path: {path}")
        seen.add(path)
        components.append(PluginComponent(type=component_type, path=path))  # type: ignore[arg-type]
    return tuple(components)


def _mcp_component(value: Any) -> PluginMCPComponent | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        path = value.strip()
    elif isinstance(value, dict) and isinstance(value.get("path"), str):
        path = value["path"].strip()
    else:
        raise ValueError("mcp must be a path string or mapping with path")
    if not path:
        raise ValueError("mcp.path must not be empty")
    return PluginMCPComponent(path=path)


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return tuple(item.strip() for item in value if item.strip())


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return dict(value)


def _validate_paths(root: Path, manifest: PluginManifest) -> None:
    for component in (*manifest.skills, *manifest.commands, *manifest.workflows):
        _resolve_inside(root, component.path)
    if manifest.mcp is not None:
        _resolve_inside(root, manifest.mcp.path)


def _resolve_inside(root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise ValueError(f"plugin component path must be relative: {relative_path}")
    resolved = (root / relative_path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"plugin component path escapes plugin directory: {relative_path}")
    return resolved
