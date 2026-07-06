"""Discover locally served Ollama and vLLM models on demand."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

LocalProvider = Literal["ollama", "vllm"]


@dataclass(frozen=True, slots=True)
class LocalModelInfo:
    """One model discovered from a local model server."""

    provider: LocalProvider
    name: str
    model: str
    base_url: str
    size: int | None = None
    modified_at: str = ""

    @property
    def registration_name(self) -> str:
        """Return a stable default models.yaml registration name."""
        normalized = self.model.replace("/", "-").replace(":", "-").replace("_", "-").lower()
        return f"{self.provider}-{normalized}"


@dataclass(frozen=True, slots=True)
class LocalDiscoveryResult:
    """Structured local model discovery result."""

    provider: LocalProvider
    base_url: str
    models: tuple[LocalModelInfo, ...] = ()
    error: str = ""
    error_type: str = ""

    @property
    def ok(self) -> bool:
        """Return true when discovery succeeded."""
        return not self.error


class LocalModelDiscovery:
    """Base class for explicit local model discovery."""

    provider: LocalProvider
    default_base_url: str

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = self._normalize_base_url(base_url or self.default_base_url)
        self.timeout = timeout
        self.transport = transport

    async def discover(self) -> LocalDiscoveryResult:
        """Discover available local models without raising network errors."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.get(self._models_url())
                response.raise_for_status()
            models = tuple(self._parse_models(response.json()))
            return LocalDiscoveryResult(provider=self.provider, base_url=self.config_base_url, models=models)
        except httpx.HTTPStatusError as exc:
            return LocalDiscoveryResult(
                provider=self.provider,
                base_url=self.config_base_url,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                error_type="http_status",
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            return LocalDiscoveryResult(
                provider=self.provider,
                base_url=self.config_base_url,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    @property
    def config_base_url(self) -> str:
        """Return the OpenAI-compatible base_url used in models.yaml."""
        raise NotImplementedError

    def _models_url(self) -> str:
        raise NotImplementedError

    def _normalize_base_url(self, base_url: str) -> str:
        return base_url.rstrip("/")

    def _parse_models(self, payload: Any) -> list[LocalModelInfo]:
        raise NotImplementedError


class OllamaDiscovery(LocalModelDiscovery):
    """Discover models from Ollama's native `/api/tags` endpoint."""

    provider: LocalProvider = "ollama"
    default_base_url = "http://localhost:11434"

    @property
    def config_base_url(self) -> str:
        return f"{self.base_url}/v1"

    def _normalize_base_url(self, base_url: str) -> str:
        normalized = base_url.rstrip("/")
        return normalized[:-3] if normalized.endswith("/v1") else normalized

    def _models_url(self) -> str:
        return f"{self.base_url}/api/tags"

    def _parse_models(self, payload: Any) -> list[LocalModelInfo]:
        raw_models = payload.get("models", []) if isinstance(payload, dict) else []
        if not isinstance(raw_models, list):
            raise ValueError("Ollama /api/tags response field 'models' must be a list")
        models: list[LocalModelInfo] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("model")
            if not isinstance(name, str) or not name.strip():
                continue
            size = item.get("size")
            models.append(
                LocalModelInfo(
                    provider="ollama",
                    name=name.strip(),
                    model=name.strip(),
                    base_url=self.config_base_url,
                    size=size if isinstance(size, int) else None,
                    modified_at=str(item.get("modified_at") or ""),
                )
            )
        return models


class VLLMDiscovery(LocalModelDiscovery):
    """Discover models from vLLM's OpenAI-compatible `/v1/models` endpoint."""

    provider: LocalProvider = "vllm"
    default_base_url = "http://localhost:8000/v1"

    @property
    def config_base_url(self) -> str:
        return self.base_url

    def _normalize_base_url(self, base_url: str) -> str:
        normalized = base_url.rstrip("/")
        return normalized if normalized.endswith("/v1") else f"{normalized}/v1"

    def _models_url(self) -> str:
        return f"{self.base_url}/models"

    def _parse_models(self, payload: Any) -> list[LocalModelInfo]:
        raw_models = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(raw_models, list):
            raise ValueError("vLLM /v1/models response field 'data' must be a list")
        models: list[LocalModelInfo] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id.strip():
                continue
            models.append(
                LocalModelInfo(
                    provider="vllm",
                    name=model_id.strip(),
                    model=model_id.strip(),
                    base_url=self.config_base_url,
                )
            )
        return models


def create_local_discovery(
    provider: str,
    *,
    base_url: str | None = None,
    timeout: float = 5.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> LocalModelDiscovery:
    """Create a local discovery adapter for a supported provider."""
    normalized = provider.strip().lower()
    if normalized == "ollama":
        return OllamaDiscovery(base_url=base_url, timeout=timeout, transport=transport)
    if normalized == "vllm":
        return VLLMDiscovery(base_url=base_url, timeout=timeout, transport=transport)
    raise ValueError(f"unsupported local discovery provider: {provider}")
