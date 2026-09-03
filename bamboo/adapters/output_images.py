"""Extract image references from final assistant output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\(([^)\s]+)\)")
HTTP_IMAGE_RE = re.compile(r"https?://[^\s\\\"'<>，。；、]+?\.(?:png|jpe?g|webp|gif|bmp|tiff?)(?:\?[^\s\\\"'<>，。；、]*)?", re.I)
LOCAL_IMAGE_RE = re.compile(r"(?:~|/|\./|\.\./)[^\s\\\"'<>，。；、]+?\.(?:png|jpe?g|webp|gif|bmp|tiff?)", re.I)


@dataclass(frozen=True, slots=True)
class OutputImage:
    """A displayable image reference found in assistant output."""

    source: str
    is_local: bool


def extract_output_images(text: str, *, base_dir: Path | None = None) -> list[OutputImage]:
    """Return unique local or HTTP image references from final output text."""
    images: list[OutputImage] = []
    seen: set[str] = set()
    occupied: list[tuple[int, int]] = []

    candidates: list[tuple[int, int, int, str]] = []
    for match in MARKDOWN_IMAGE_RE.finditer(text or ""):
        candidates.append((match.start(), match.end(), 0, _clean_source(match.group(1))))
    for match in HTTP_IMAGE_RE.finditer(text or ""):
        candidates.append((match.start(), match.end(), 1, _clean_source(match.group(0))))
    for match in LOCAL_IMAGE_RE.finditer(text or ""):
        candidates.append((match.start(), match.end(), 2, _clean_source(match.group(0))))

    for start, end, _, source in sorted(candidates):
        if _overlaps((start, end), occupied):
            continue
        occupied.append((start, end))
        _append_image(images, seen, source, base_dir=base_dir)

    return images


def text_without_output_image_markdown(text: str) -> str:
    """Remove standalone markdown image lines before sending text-only channels."""
    lines = []
    for line in (text or "").splitlines():
        if MARKDOWN_IMAGE_RE.fullmatch(line.strip()):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _append_image(images: list[OutputImage], seen: set[str], source: str, *, base_dir: Path | None) -> None:
    if not source or source in seen:
        return
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        seen.add(source)
        images.append(OutputImage(source=source, is_local=False))
        return
    if source.startswith("data:image/"):
        seen.add(source)
        images.append(OutputImage(source=source, is_local=False))
        return
    path = Path(source).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    normalized = str(path.resolve(strict=False))
    if normalized in seen:
        return
    seen.add(normalized)
    images.append(OutputImage(source=normalized, is_local=True))


def _clean_source(source: str) -> str:
    return source.strip().strip("<>").rstrip(".,;:!?)]}，。；：！？）】")


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in spans)
