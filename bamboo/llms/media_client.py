"""Media generation client interfaces and shared helpers."""

from __future__ import annotations

import base64
import mimetypes
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from bamboo.llms.config import ModelConfig, ModelConfigError


@dataclass(frozen=True, slots=True)
class MediaRequest:
    """Provider-agnostic media generation request."""

    input: dict[str, Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    output_dir: str = "~/.bamboo/workspace/media-generation"
    timeout_seconds: float = 600
    poll_interval_seconds: float = 2
    download: bool = True


@dataclass(frozen=True, slots=True)
class MediaResponse:
    """Provider-agnostic media generation response."""

    content: str
    urls: list[str] = field(default_factory=list)
    saved_paths: list[str] = field(default_factory=list)
    task_id: str = ""
    status: str = "SUCCEEDED"
    metadata: dict[str, Any] = field(default_factory=dict)


class MediaClient(ABC):
    """Base interface for provider-specific media clients."""

    def __init__(self, config: ModelConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.config = config
        self.transport = transport

    @abstractmethod
    async def generate(self, request: MediaRequest) -> MediaResponse:
        """Generate or edit media and return normalized output metadata."""


def create_media_client(config: ModelConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> MediaClient:
    """Create the media client declared by models.yaml extra_body.protocol."""
    protocol = str(config.extra_body.get("protocol") or "").strip()
    if not protocol and config.provider == "aliyun":
        protocol = "dashscope_async"
    if protocol == "dashscope_async":
        from bamboo.llms.providers.aliyun import DashScopeAsyncMediaClient

        return DashScopeAsyncMediaClient(config, transport=transport)
    if protocol == "openrouter_images":
        from bamboo.llms.providers.openrouter import OpenRouterImagesClient

        return OpenRouterImagesClient(config, transport=transport)
    raise ModelConfigError(
        f"Model '{config.name}' uses unsupported media protocol '{protocol or '(empty)'}'. "
        "Configure extra_body.protocol to a supported protocol."
    )


def merge_mappings(first: Any, second: Mapping[str, Any]) -> dict[str, Any]:
    """Merge optional model default parameters with request-time parameters."""
    result = dict(first) if isinstance(first, Mapping) else {}
    result.update(second)
    return result


def apply_input_field_mapping(input_payload: Mapping[str, Any], field_mapping: Any) -> dict[str, Any]:
    """Apply provider-specific input field names declared in model extra_body."""
    if not isinstance(field_mapping, Mapping):
        return dict(input_payload)
    mapped: dict[str, Any] = {}
    for key, value in input_payload.items():
        target_key = field_mapping.get(key, key)
        if isinstance(target_key, str) and target_key:
            mapped[target_key] = value
    return mapped


def join_url(base_url: str, path: str) -> str:
    """Join a base URL and endpoint path."""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def nested_get(data: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    """Read a nested mapping value."""
    current: Any = data
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def collect_urls(value: Any) -> list[str]:
    """Collect URL-like media outputs from a provider response."""
    urls: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if key in {"url", "image_url", "video_url", "output_url"} and isinstance(child, str) and _is_url(child):
                    urls.append(child)
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return list(dict.fromkeys(urls))


async def download_urls(client: httpx.AsyncClient, urls: list[str], *, output_dir: str) -> list[str]:
    """Download media URLs to the configured output directory."""
    root = Path(output_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    for index, url in enumerate(urls, start=1):
        response = await client.get(url)
        response.raise_for_status()
        suffix = _extension_from_response(url, response.headers.get("content-type", ""))
        path = root / f"media-{int(time.time())}-{index}{suffix}"
        path.write_bytes(response.content)
        saved_paths.append(str(path))
    return saved_paths


def save_base64_images(data: Any, *, output_dir: str) -> list[str]:
    """Save b64_json images from a provider response to local files."""
    root = Path(output_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    for index, item in enumerate(_collect_base64_images(data), start=1):
        raw = item["b64_json"]
        if raw.startswith("data:") and "," in raw:
            raw = raw.split(",", 1)[1]
        image_bytes = base64.b64decode(raw)
        suffix = _extension_from_media_type(item.get("media_type", "image/png"))
        path = root / f"media-{int(time.time())}-{index}{suffix}"
        path.write_bytes(image_bytes)
        saved_paths.append(str(path))
    return saved_paths


def http_error_message(response: httpx.Response) -> str:
    """Format a concise provider HTTP error."""
    try:
        data = response.json()
    except ValueError:
        data = {}
    message = ""
    if isinstance(data, Mapping):
        error = data.get("message") or data.get("code") or data.get("error")
        if isinstance(error, Mapping):
            message = str(error.get("message") or error.get("code") or "")
        elif error:
            message = str(error)
    return f"Media generation request failed with HTTP {response.status_code}: {message or response.text[:500]}"


def redact_response(data: Any) -> Any:
    """Redact obvious key-like fields before returning raw provider metadata."""
    if isinstance(data, Mapping):
        return {key: ("<redacted>" if "key" in str(key).lower() else redact_response(value)) for key, value in data.items()}
    if isinstance(data, list):
        return [redact_response(item) for item in data]
    return data


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _collect_base64_images(value: Any) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            raw = item.get("b64_json")
            if isinstance(raw, str) and raw:
                images.append(
                    {
                        "b64_json": raw,
                        "media_type": str(item.get("media_type") or item.get("mime_type") or "image/png"),
                    }
                )
                return
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return images


def _extension_from_response(url: str, content_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix
    if suffix:
        return suffix
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
    return guessed or ".bin"


def _extension_from_media_type(media_type: str) -> str:
    return mimetypes.guess_extension(media_type.split(";", 1)[0].strip()) or ".png"
