"""Generic media generation tools backed by configured model clients."""

from __future__ import annotations

import base64
import mimetypes
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from bamboo.helpers.config import BambooConfig
from bamboo.llms.config import ModelCatalog, ModelConfig, ModelConfigError
from bamboo.llms.media_client import MediaRequest, create_media_client
from bamboo.tools.buildin.base import Tool, ToolResult

_DEFAULT_OUTPUT_DIR = "~/.bamboo/workspace/media-generation"


class _MediaGenerationTool(Tool):
    """Shared tool-side config and validation for media generation."""

    risk_level = "network"
    tags = ("media", "network")
    expected_model_type = ""
    tool_config_key = ""

    def __init__(
        self,
        *,
        config_document: Mapping[str, Any] | None = None,
        tools_document: Mapping[str, Any] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config_document = config_document
        self._tools_document = tools_document
        self._transport = transport

    async def _run_task(
        self,
        *,
        model_name: str,
        input_payload: dict[str, Any],
        parameters: dict[str, Any],
        output_dir: str,
        timeout_seconds: float,
        poll_interval_seconds: float,
        download: bool,
    ) -> ToolResult:
        try:
            model_config = self._resolve_model(model_name)
            client = create_media_client(model_config, transport=self._transport)
            response = await client.generate(
                MediaRequest(
                    input=input_payload,
                    parameters=parameters,
                    output_dir=output_dir,
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                    download=download,
                )
            )
        except (ModelConfigError, RuntimeError, ValueError) as exc:
            return ToolResult(content="", success=False, error=str(exc))

        success = response.status == "SUCCEEDED"
        metadata = {
            "task_id": response.task_id,
            "status": response.status,
            "urls": response.urls,
            "saved_paths": response.saved_paths,
            "model": model_config.name,
            **response.metadata,
        }
        return ToolResult(
            content=response.content,
            success=success,
            error="" if success else response.content,
            metadata=metadata,
        )

    def _tool_settings(self) -> dict[str, Any]:
        document = self._tools_document
        if document is None:
            document = BambooConfig().get("tools", {})
        raw = document.get("media_generation", {}) if isinstance(document, Mapping) else {}
        if not isinstance(raw, Mapping) and isinstance(document, Mapping):
            raw = document.get("aliyun_media", {})
        return dict(raw) if isinstance(raw, Mapping) else {}

    def _default_model_name(self) -> str:
        value = self._tool_settings().get(self.tool_config_key, "")
        return str(value).strip()

    def timeout_override_seconds(self) -> float | None:
        settings = self._tool_settings()
        value = settings.get("tool_call_timeout_seconds", settings.get("timeout_seconds"))
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            return None
        return float(value)

    def _resolve_model(self, model_name: str) -> ModelConfig:
        document = self._config_document
        if document is None:
            document = BambooConfig().get("models", {})
        if not isinstance(document, Mapping):
            raise ModelConfigError("models.yaml is not loaded")
        config = ModelCatalog.from_mapping(document).models.get(model_name)
        if config is None:
            raise ModelConfigError(f"Model '{model_name}' is not registered in models.yaml")
        if config.model_type != self.expected_model_type:
            raise ModelConfigError(
                f"Model '{model_name}' must use model_type '{self.expected_model_type}', got '{config.model_type}'"
            )
        return config.resolve_environment()


class TextToImageTool(_MediaGenerationTool):
    """Generate images through a configured text-to-image model."""

    name = "text_to_image"
    description = "Generate image assets with a text-to-image model configured in models.yaml."
    expected_model_type = "image_generation"
    tool_config_key = "text_to_image_model"

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image prompt."},
                "model": {"type": "string", "description": "Optional models.yaml registration name."},
                "size": {"type": "string", "description": "Optional output size, for example 1024*1024."},
                "n": {"type": "integer", "description": "Optional number of images."},
                "parameters": {"type": "object", "description": "Optional provider-specific parameters."},
                "output_dir": {"type": "string", "description": "Optional local directory for downloaded assets."},
                "download": {"type": "boolean", "description": "Download generated assets locally when true."},
            },
            "required": ["prompt"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        prompt = str(kwargs.get("prompt") or "").strip()
        if not prompt:
            return ToolResult(content="", success=False, error="prompt is required")
        settings = self._tool_settings()
        parameters = _mapping_arg(kwargs.get("parameters"))
        if kwargs.get("size"):
            parameters["size"] = str(kwargs["size"])
        if kwargs.get("n") is not None:
            parameters["n"] = int(kwargs["n"])
        return await self._run_task(
            model_name=str(kwargs.get("model") or self._default_model_name()).strip(),
            input_payload={"prompt": prompt},
            parameters=parameters,
            output_dir=str(kwargs.get("output_dir") or settings.get("output_dir") or _DEFAULT_OUTPUT_DIR),
            timeout_seconds=float(settings.get("timeout_seconds", 600)),
            poll_interval_seconds=float(settings.get("poll_interval_seconds", 2)),
            download=bool(kwargs.get("download", True)),
        )


class ImageEditTool(_MediaGenerationTool):
    """Edit an image through a configured image-edit model."""

    name = "image_edit"
    description = "Edit an existing image with an image editing model configured in models.yaml."
    expected_model_type = "image_edit"
    tool_config_key = "image_edit_model"

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Editing instruction."},
                "image_url": {"type": "string", "description": "Source image URL."},
                "image_path": {"type": "string", "description": "Optional local source image path converted to data URL."},
                "function": {"type": "string", "description": "Optional provider-specific edit function."},
                "model": {"type": "string", "description": "Optional models.yaml registration name."},
                "parameters": {"type": "object", "description": "Optional provider-specific parameters."},
                "output_dir": {"type": "string", "description": "Optional local directory for downloaded assets."},
                "download": {"type": "boolean", "description": "Download generated assets locally when true."},
            },
            "required": ["prompt"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        prompt = str(kwargs.get("prompt") or "").strip()
        image_url = str(kwargs.get("image_url") or "").strip()
        image_path = str(kwargs.get("image_path") or "").strip()
        if not prompt:
            return ToolResult(content="", success=False, error="prompt is required")
        if not image_url and not image_path:
            return ToolResult(content="", success=False, error="image_url or image_path is required")
        if image_path and not image_url:
            try:
                image_url = _local_image_to_data_url(image_path)
            except OSError as exc:
                return ToolResult(content="", success=False, error=f"Cannot read image_path: {exc}")
        settings = self._tool_settings()
        return await self._run_task(
            model_name=str(kwargs.get("model") or self._default_model_name()).strip(),
            input_payload={
                "function": str(kwargs.get("function") or "description_edit"),
                "prompt": prompt,
                "image_url": image_url,
            },
            parameters=_mapping_arg(kwargs.get("parameters")),
            output_dir=str(kwargs.get("output_dir") or settings.get("output_dir") or _DEFAULT_OUTPUT_DIR),
            timeout_seconds=float(settings.get("timeout_seconds", 600)),
            poll_interval_seconds=float(settings.get("poll_interval_seconds", 2)),
            download=bool(kwargs.get("download", True)),
        )


class TextToVideoTool(_MediaGenerationTool):
    """Generate video through a configured text-to-video model."""

    name = "text_to_video"
    description = "Generate video assets with a text-to-video model configured in models.yaml."
    expected_model_type = "video_generation"
    tool_config_key = "text_to_video_model"

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Video prompt."},
                "model": {"type": "string", "description": "Optional models.yaml registration name."},
                "parameters": {"type": "object", "description": "Optional provider-specific parameters."},
                "output_dir": {"type": "string", "description": "Optional local directory for downloaded assets."},
                "download": {"type": "boolean", "description": "Download generated assets locally when true."},
            },
            "required": ["prompt"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        prompt = str(kwargs.get("prompt") or "").strip()
        if not prompt:
            return ToolResult(content="", success=False, error="prompt is required")
        settings = self._tool_settings()
        return await self._run_task(
            model_name=str(kwargs.get("model") or self._default_model_name()).strip(),
            input_payload={"prompt": prompt},
            parameters=_mapping_arg(kwargs.get("parameters")),
            output_dir=str(kwargs.get("output_dir") or settings.get("output_dir") or _DEFAULT_OUTPUT_DIR),
            timeout_seconds=float(settings.get("timeout_seconds", 600)),
            poll_interval_seconds=float(settings.get("poll_interval_seconds", 2)),
            download=bool(kwargs.get("download", True)),
        )


def _mapping_arg(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _local_image_to_data_url(path: str) -> str:
    image_path = Path(path).expanduser()
    media_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{data}"
