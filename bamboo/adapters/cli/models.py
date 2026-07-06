"""CLI helpers for local model discovery."""

from __future__ import annotations

from pathlib import Path

from bamboo.llms.local_discovery import LocalDiscoveryResult, create_local_discovery
from bamboo.llms.model_config_writer import ModelConfigWriteResult, ModelConfigWriter, render_models_yaml_snippet


async def discover_local_models(provider: str, *, base_url: str | None = None, timeout: float = 5.0) -> LocalDiscoveryResult:
    """Run explicit local model discovery for one provider."""
    return await create_local_discovery(provider, base_url=base_url, timeout=timeout).discover()


def format_discovery_result(result: LocalDiscoveryResult) -> str:
    """Render discovery results for terminal output."""
    if not result.ok:
        return f"{result.provider} discovery failed at {result.base_url}: {result.error}"
    if not result.models:
        return f"{result.provider} discovery succeeded at {result.base_url}, but no models were returned."
    lines = [f"{result.provider} discovery succeeded at {result.base_url}", ""]
    for model in result.models:
        suffix = f" size={model.size}" if model.size is not None else ""
        lines.append(f"- {model.registration_name}: {model.model}{suffix}")
    lines.extend(["", "models.yaml snippet:", render_models_yaml_snippet(result.models)])
    return "\n".join(lines)


def write_discovery_result(
    result: LocalDiscoveryResult,
    *,
    config_path: Path,
    set_default: bool = False,
    replace: bool = False,
) -> ModelConfigWriteResult:
    """Write a successful discovery result to a models.yaml file."""
    if not result.ok:
        raise ValueError(f"cannot write failed discovery result: {result.error}")
    if not result.models:
        raise ValueError("cannot write discovery result with no models")
    return ModelConfigWriter(config_path).write_discovered(
        result.models,
        set_default=set_default,
        replace=replace,
    )
