"""Helpers for serializing image inputs to LLM provider payloads."""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

from bamboo.llms.base import LLMImage
from bamboo.llms.config import ModelConfigError

MAX_IMAGE_BYTES = 20 * 1024 * 1024
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
_HTTP_IMAGE_PATTERN = re.compile(r"https?://[^\s\\\"'<>，。；、]+?\.(?:png|jpe?g|webp|gif|bmp|tiff?)(?:\?[^\s\\\"'<>，。；、]*)?", re.I)
_ABSOLUTE_IMAGE_PATH_PATTERN = re.compile(r"(?:~|/)[^\s\\\"'<>，。；、]+?\.(?:png|jpe?g|webp|gif|bmp|tiff?)", re.I)


def image_from_source(source: str, *, detail: str = "auto") -> LLMImage:
    """Create an image reference from a local path, URL, or data URL."""
    normalized_source = source.strip()
    if not normalized_source:
        raise ModelConfigError("image source cannot be empty")
    media_type = ""
    if _is_data_url(normalized_source):
        media_type = _media_type_from_data_url(normalized_source)
    elif not _is_http_url(normalized_source):
        media_type = _guess_media_type(Path(normalized_source))
    return LLMImage(source=normalized_source, media_type=media_type, detail=detail or "auto")


def images_from_text(text: str) -> list[LLMImage]:
    """Extract image paths or URLs mentioned in natural language text."""
    images: list[LLMImage] = []
    seen: set[str] = set()
    occupied_spans: list[tuple[int, int]] = []
    for match in _HTTP_IMAGE_PATTERN.finditer(text):
        source = _strip_trailing_punctuation(match.group(0))
        if source in seen:
            continue
        seen.add(source)
        occupied_spans.append(match.span())
        images.append(image_from_source(source))
    for match in _ABSOLUTE_IMAGE_PATH_PATTERN.finditer(text):
        if _overlaps_any(match.span(), occupied_spans):
            continue
        source = _strip_trailing_punctuation(match.group(0))
        if source in seen:
            continue
        seen.add(source)
        images.append(image_from_source(source))
    return images


def merge_images(*groups: list[LLMImage]) -> list[LLMImage]:
    """Merge explicit and text-extracted images by source."""
    merged: list[LLMImage] = []
    seen: set[str] = set()
    for group in groups:
        for image in group:
            if image.source in seen:
                continue
            seen.add(image.source)
            merged.append(image)
    return merged


def to_openai_image_url(image: LLMImage) -> dict[str, object]:
    """Serialize an image for OpenAI-compatible chat completions."""
    image_url: dict[str, str] = {
        "url": _as_data_url(image) if _is_local_path(image.source) else image.source,
    }
    if image.detail:
        image_url["detail"] = image.detail
    return {"type": "image_url", "image_url": image_url}


def to_anthropic_image_block(image: LLMImage) -> dict[str, object]:
    """Serialize a local/data image for Anthropic Messages."""
    if _is_http_url(image.source):
        raise ModelConfigError("Anthropic image input currently supports local files or data URLs, not HTTP URLs")
    data_url = image.source if _is_data_url(image.source) else _as_data_url(image)
    media_type, encoded = _split_data_url(data_url)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": encoded,
        },
    }


def image_summary(images: list[LLMImage]) -> str:
    """Render image inputs without embedding binary data in logs."""
    if not images:
        return ""
    return "\n".join(
        f"[image {index + 1}] source={_redacted_source(image.source)} media_type={image.media_type or 'auto'}"
        for index, image in enumerate(images)
    )


def _as_data_url(image: LLMImage) -> str:
    path = Path(image.source).expanduser()
    if not path.is_file():
        raise ModelConfigError(f"image file not found: {image.source}")
    size = path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ModelConfigError(f"image file is too large: {image.source} ({size} bytes)")
    media_type = image.media_type or _guess_media_type(path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _guess_media_type(path: Path) -> str:
    media_type, _ = mimetypes.guess_type(str(path))
    if media_type and media_type.startswith("image/"):
        return media_type
    return "image/png"


def _is_local_path(source: str) -> bool:
    return not _is_http_url(source) and not _is_data_url(source)


def _is_http_url(source: str) -> bool:
    return urlparse(source).scheme in {"http", "https"}


def _is_data_url(source: str) -> bool:
    return source.startswith("data:image/")


def _media_type_from_data_url(source: str) -> str:
    media_type, _ = _split_data_url(source)
    return media_type


def _split_data_url(source: str) -> tuple[str, str]:
    header, separator, encoded = source.partition(",")
    if not separator or ";base64" not in header:
        raise ModelConfigError("image data URL must be base64 encoded")
    media_type = header.removeprefix("data:").split(";", 1)[0]
    if not media_type.startswith("image/"):
        raise ModelConfigError("image data URL must use an image/* media type")
    return media_type, encoded


def _redacted_source(source: str) -> str:
    if _is_data_url(source):
        media_type = _media_type_from_data_url(source)
        return f"data:{media_type};base64,[redacted]"
    return source


def _strip_trailing_punctuation(source: str) -> str:
    return source.rstrip(".,;:!?)]}，。；：！？）】")


def _overlaps_any(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in spans)
