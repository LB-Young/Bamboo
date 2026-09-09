#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    import fitz
except ImportError as exc:  # pragma: no cover - exercised only in missing local dependency environments.
    raise SystemExit("PyMuPDF is required. Install it with: python3 -m pip install PyMuPDF") from exc

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - exercised only in missing local dependency environments.
    raise SystemExit("Pillow is required. Install it with: python3 -m pip install Pillow") from exc


DEFAULT_MODELS_DIR = Path("/Users/liubaoyang/Documents/YoungL/models")
DEFAULT_LAYOUT_MODEL = DEFAULT_MODELS_DIR / "DocLayout-YOLO-DocStructBench" / "doclayout_yolo_docstructbench_imgsz1024.pt"
WORKFLOW_NAME = "local-pdf-to-markdown"
TEXT_TYPES = {"title", "plain text", "text", "abandon", "figure_caption", "table_caption", "caption", "section"}
FIGURE_TYPES = {"figure", "figure_body", "image"}
TABLE_TYPES = {"table"}
CAPTION_TYPES = {"figure_caption", "table_caption", "caption"}
DROP_TYPES = {"header", "footer", "page_number", "page-footer", "page-header"}


@dataclass
class Block:
    id: str
    page: int
    type: str
    bbox: list[float]
    text: str = ""
    source: str = "native_pdf"
    score: float | None = None
    asset_path: str = ""
    caption: str = ""
    level: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    config = load_workflow_variables()
    dpi = args.dpi or positive_int(config.get("PDF2MD_DPI"), 180)
    layout_model = args.layout_model or Path(
        str(config.get("PDF2MD_LAYOUT_MODEL") or DEFAULT_LAYOUT_MODEL)
    )
    layout_device = args.layout_device or str(config.get("PDF2MD_LAYOUT_DEVICE") or "cpu")
    enable_ocr = str(config.get("PDF2MD_ENABLE_OCR") or "auto").strip().lower()
    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise SystemExit(f"Input must be a PDF file: {pdf_path}")

    output_md = resolve_output_path(pdf_path, args.output)
    output_dir = output_md.parent.resolve()
    pages_dir = output_dir / "pages"
    layout_dir = output_dir / "layout"
    figures_dir = output_dir / "assets" / "figures"
    tables_dir = output_dir / "assets" / "tables"
    for directory in (output_dir, pages_dir, layout_dir, figures_dir, tables_dir):
        directory.mkdir(parents=True, exist_ok=True)

    document = convert_pdf(
        pdf_path=pdf_path,
        output_md=output_md,
        output_dir=output_dir,
        pages_dir=pages_dir,
        layout_dir=layout_dir,
        figures_dir=figures_dir,
        tables_dir=tables_dir,
        dpi=dpi,
        layout_model=layout_model.expanduser().resolve(),
        layout_device=layout_device,
        enable_ocr=enable_ocr,
        config=config,
    )

    ir_path = output_dir / "document.json"
    ir_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(document, output_dir), encoding="utf-8")

    print(f"Markdown: {output_md}")
    print(f"IR: {ir_path}")
    print(f"OutputDir: {output_dir}")
    print(f"Pages: {document['metadata']['pages']}")
    print(f"Mode: {document['metadata']['mode']}")
    if document["metadata"].get("layout_model"):
        print(f"LayoutModel: {document['metadata']['layout_model']}")
    if document["metadata"].get("warnings"):
        print("Warnings:")
        for warning in document["metadata"]["warnings"]:
            print(f"- {warning}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    tokens: list[str] = []
    for item in argv:
        tokens.extend(shlex.split(item))
    parser = argparse.ArgumentParser(description="Convert a local PDF to structured Markdown.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--dpi", type=int)
    parser.add_argument("--layout-model", type=Path)
    parser.add_argument("--layout-device")
    return parser.parse_args(tokens)


def load_workflow_variables() -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for config_path in workflow_config_paths():
        data = read_yaml_mapping(config_path)
        workflows = data.get("workflows")
        if not isinstance(workflows, dict):
            continue
        workflow_config = workflows.get(WORKFLOW_NAME)
        if not isinstance(workflow_config, dict):
            continue
        variables = workflow_config.get("variables")
        if isinstance(variables, dict):
            merged.update(variables)
    return merged


def workflow_config_paths() -> list[Path]:
    package_root = Path(__file__).resolve().parents[4]
    return [
        package_root / "configs" / "workflows_buildin.yaml",
        Path.home() / ".bamboo" / "configs" / "workflows_buildin.yaml",
    ]


def read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def resolve_output_path(pdf_path: Path, output: Path | None) -> Path:
    if output is not None:
        output_path = output.expanduser()
        if output_path.suffix.lower() != ".md":
            output_path = output_path / f"{pdf_path.stem}.md"
        return output_path.resolve()
    return (pdf_path.parent / pdf_path.stem / f"{pdf_path.stem}.md").resolve()


def convert_pdf(
    *,
    pdf_path: Path,
    output_md: Path,
    output_dir: Path,
    pages_dir: Path,
    layout_dir: Path,
    figures_dir: Path,
    tables_dir: Path,
    dpi: int,
    layout_model: Path,
    layout_device: str,
    enable_ocr: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    layout_detector, layout_warning = load_layout_detector(layout_model, layout_device)
    ocr_engine, ocr_warning = load_ocr_engine(enable_ocr, config)
    warnings = [warning for warning in (layout_warning, ocr_warning) if warning]
    all_blocks: list[Block] = []
    image_assets = 0
    layout_assets = 0
    scanned_pages = 0

    for page_index, page in enumerate(doc, start=1):
        page_png = render_page(page, page_index, pages_dir, dpi)
        native_blocks = native_text_blocks(page, page_index)
        layout_blocks = detect_layout(layout_detector, page_png, page_index, layout_dir, dpi, layout_device)
        page_blocks = assign_layout_text(layout_blocks, native_blocks) if layout_blocks else native_blocks
        if not reliable_text(page_blocks):
            scanned_pages += 1
            ocr_text = run_ocr(ocr_engine, page_png)
            if ocr_text:
                page_rect = page.rect
                page_blocks.append(
                    Block(
                        id=f"p{page_index:03d}_ocr001",
                        page=page_index,
                        type="text",
                        bbox=[0, 0, float(page_rect.width), float(page_rect.height)],
                        text=ocr_text,
                        source="ocr",
                    )
                )
        page_blocks = filter_noise_blocks(page_blocks, page.rect)
        page_layout_assets = crop_layout_assets(page_png, page_blocks, output_dir, figures_dir, tables_dir)
        layout_assets += page_layout_assets
        fallback_image_blocks = []
        if page_layout_assets == 0:
            fallback_image_blocks = extract_pdf_image_blocks(page, page_index, native_image_blocks(page, page_index), output_dir, figures_dir)
            image_assets += len(fallback_image_blocks)
        all_blocks.extend(restore_reading_order(page_blocks, page.rect.width))
        all_blocks.extend(fallback_image_blocks)

    content = build_document_ir(all_blocks)
    mode = "mixed"
    if scanned_pages == 0:
        mode = "digital"
    elif scanned_pages == len(doc):
        mode = "scanned"
    return {
        "metadata": {
            "source": str(pdf_path),
            "output": str(output_md),
            "pages": len(doc),
            "mode": mode,
            "dpi": dpi,
            "layout_model": str(layout_model) if layout_detector else "",
            "ocr_enabled": ocr_engine is not None,
            "assets": {"layout_crops": layout_assets, "pdf_images": image_assets},
            "warnings": warnings,
        },
        "content": [block_to_ir(block, output_dir) for block in content],
    }


def render_page(page: fitz.Page, page_index: int, pages_dir: Path, dpi: int) -> Path:
    scale = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    page_png = pages_dir / f"page_{page_index:03d}.png"
    pix.save(page_png)
    return page_png


def native_text_blocks(page: fitz.Page, page_index: int) -> list[Block]:
    data = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)
    blocks: list[Block] = []
    for block_index, raw in enumerate(data.get("blocks", []), start=1):
        if raw.get("type") != 0:
            continue
        text, max_size, flags = text_from_block(raw)
        text = normalize_text(text)
        if not text:
            continue
        block_type = infer_text_type(text, max_size, page.rect.height, raw.get("bbox", [0, 0, 0, 0]))
        blocks.append(
            Block(
                id=f"p{page_index:03d}_n{block_index:03d}",
                page=page_index,
                type=block_type,
                bbox=[float(v) for v in raw.get("bbox", [0, 0, 0, 0])],
                text=text,
                source="native_pdf",
                level=heading_level(text, block_type),
                meta={"font_size": max_size, "font_flags": flags},
            )
        )
    return blocks


def native_image_blocks(page: fitz.Page, page_index: int) -> list[Block]:
    data = page.get_text("dict")
    blocks: list[Block] = []
    for block_index, raw in enumerate(data.get("blocks", []), start=1):
        if raw.get("type") != 1:
            continue
        bbox = [float(v) for v in raw.get("bbox", [0, 0, 0, 0])]
        area = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
        if area < 2500:
            continue
        blocks.append(
            Block(
                id=f"p{page_index:03d}_img{block_index:03d}",
                page=page_index,
                type="figure",
                bbox=bbox,
                source="pdf_image",
            )
        )
    return blocks


def text_from_block(raw: dict[str, Any]) -> tuple[str, float, int]:
    lines: list[str] = []
    max_size = 0.0
    flags = 0
    for line in raw.get("lines", []):
        spans = []
        for span in line.get("spans", []):
            spans.append(span.get("text", ""))
            max_size = max(max_size, float(span.get("size", 0) or 0))
            flags |= int(span.get("flags", 0) or 0)
        line_text = "".join(spans).strip()
        if line_text:
            lines.append(line_text)
    return "\n".join(lines), max_size, flags


def load_layout_detector(model_path: Path, device: str) -> tuple[Any | None, str]:
    if not model_path.is_file():
        return None, f"DocLayout-YOLO model not found: {model_path}; using PyMuPDF fallback."
    try:
        from doclayout_yolo import YOLOv10  # type: ignore
    except ImportError:
        return None, "doclayout_yolo package is not installed; using PyMuPDF fallback."
    try:
        return YOLOv10(str(model_path)), ""
    except Exception as exc:  # pragma: no cover - model/runtime dependent.
        return None, f"DocLayout-YOLO failed to load: {exc}; using PyMuPDF fallback."


def detect_layout(detector: Any | None, page_png: Path, page_index: int, layout_dir: Path, dpi: int, device: str) -> list[Block]:
    if detector is None:
        (layout_dir / f"page_{page_index:03d}.json").write_text("[]\n", encoding="utf-8")
        return []
    result_blocks: list[Block] = []
    try:
        results = detector.predict(str(page_png), imgsz=1024, conf=0.2, device=device, verbose=False)
    except TypeError:
        results = detector.predict(str(page_png), imgsz=1024, conf=0.2, device=device)
    except Exception:
        results = []
    if not results:
        (layout_dir / f"page_{page_index:03d}.json").write_text("[]\n", encoding="utf-8")
        return []
    image_width, image_height = Image.open(page_png).size
    page_blocks = []
    result = results[0]
    names = getattr(result, "names", {}) or {}
    boxes = getattr(result, "boxes", None)
    if boxes is not None:
        for block_index, box in enumerate(boxes, start=1):
            xyxy = [float(v) for v in box.xyxy[0].tolist()]
            cls_id = int(box.cls[0].item()) if getattr(box, "cls", None) is not None else -1
            score = float(box.conf[0].item()) if getattr(box, "conf", None) is not None else None
            raw_type = str(names.get(cls_id, cls_id)).lower().replace(" ", "_")
            block = Block(
                id=f"p{page_index:03d}_l{block_index:03d}",
                page=page_index,
                type=map_layout_type(raw_type),
                bbox=image_bbox_to_pdf_bbox(xyxy, image_width, image_height, result, dpi),
                score=score,
                source="layout",
                meta={"raw_type": raw_type, "image_bbox": xyxy},
            )
            result_blocks.append(block)
            page_blocks.append(asdict(block))
    (layout_dir / f"page_{page_index:03d}.json").write_text(
        json.dumps(page_blocks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result_blocks


def image_bbox_to_pdf_bbox(image_bbox: list[float], image_width: int, image_height: int, result: Any, dpi: int) -> list[float]:
    orig_shape = getattr(result, "orig_shape", None)
    if orig_shape and len(orig_shape) >= 2:
        image_height = int(orig_shape[0])
        image_width = int(orig_shape[1])
    # PyMuPDF rendered pages use a uniform scale. Recovering exact PDF coords happens later by overlap;
    # layout crop code keeps the original image bbox in metadata for pixel-accurate crops.
    scale_x = 72.0 / dpi
    scale_y = 72.0 / dpi
    return [image_bbox[0] * scale_x, image_bbox[1] * scale_y, image_bbox[2] * scale_x, image_bbox[3] * scale_y]


def assign_layout_text(layout_blocks: list[Block], native_blocks: list[Block]) -> list[Block]:
    assigned: list[Block] = []
    for layout in layout_blocks:
        if layout.type in DROP_TYPES | FIGURE_TYPES | TABLE_TYPES:
            assigned.append(layout)
            continue
        overlaps = [block for block in native_blocks if overlap_ratio(layout.bbox, block.bbox) > 0.15]
        text = "\n".join(block.text for block in restore_reading_order(overlaps, 1000) if block.text)
        if text:
            layout.text = normalize_text(text)
            layout.source = "layout+native_pdf"
            layout.level = heading_level(layout.text, layout.type)
        assigned.append(layout)
    used_ids = {block.id for block in assigned if block.text}
    for native in native_blocks:
        if native.id not in used_ids and not any(overlap_ratio(native.bbox, block.bbox) > 0.5 for block in assigned):
            assigned.append(native)
    return assigned


def load_ocr_engine(enable_ocr: str, config: dict[str, Any]) -> tuple[Any | None, str]:
    if enable_ocr in {"0", "false", "no", "off", "disabled"}:
        return None, "OCR is disabled by workflows_buildin.yaml."
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError:
        return None, "PaddleOCR is not installed; scanned pages may not contain OCR text."
    kwargs: dict[str, Any] = {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
    }
    detection_dir = configured_model_dir(config.get("PDF2MD_OCR_DETECTION_MODEL_DIR"))
    recognition_dir = configured_model_dir(config.get("PDF2MD_OCR_RECOGNITION_MODEL_DIR"))
    if detection_dir:
        kwargs["text_detection_model_dir"] = str(detection_dir)
    elif config.get("PDF2MD_OCR_DETECTION_MODEL_NAME"):
        kwargs["text_detection_model_name"] = str(config["PDF2MD_OCR_DETECTION_MODEL_NAME"])
    if recognition_dir:
        kwargs["text_recognition_model_dir"] = str(recognition_dir)
    elif config.get("PDF2MD_OCR_RECOGNITION_MODEL_NAME"):
        kwargs["text_recognition_model_name"] = str(config["PDF2MD_OCR_RECOGNITION_MODEL_NAME"])
    try:
        return PaddleOCR(**kwargs), ""
    except ValueError:
        kwargs.pop("text_detection_model_dir", None)
        kwargs.pop("text_recognition_model_dir", None)
        return PaddleOCR(**kwargs), ""
    except Exception as exc:  # pragma: no cover - OCR runtime dependent.
        return None, f"PaddleOCR failed to initialize: {exc}"


def configured_model_dir(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value)).expanduser()
    return path.resolve() if path.is_dir() else None


def run_ocr(ocr_engine: Any | None, image_path: Path) -> str:
    if ocr_engine is None:
        return ""
    try:
        result = ocr_engine.predict(str(image_path))
    except AttributeError:
        result = ocr_engine.ocr(str(image_path), cls=False)
    except Exception:
        return ""
    return normalize_text(extract_ocr_text(result))


def extract_ocr_text(result: Any) -> str:
    if isinstance(result, list):
        chunks: list[str] = []
        for item in result:
            if isinstance(item, dict):
                chunks.extend(str(text) for text in item.get("rec_texts", []) if text)
            elif isinstance(item, list):
                for row in item:
                    if isinstance(row, list) and len(row) >= 2 and isinstance(row[1], (tuple, list)):
                        chunks.append(str(row[1][0]))
        return "\n".join(chunks)
    return ""


def reliable_text(blocks: list[Block]) -> bool:
    return sum(len(block.text.strip()) for block in blocks) >= 80


def filter_noise_blocks(blocks: list[Block], rect: fitz.Rect) -> list[Block]:
    kept = []
    for block in blocks:
        if block.type in DROP_TYPES:
            continue
        text = block.text.strip()
        if text and re.fullmatch(r"\d{1,4}", text):
            continue
        y0, y1 = block.bbox[1], block.bbox[3]
        if text and (y1 < rect.height * 0.04 or y0 > rect.height * 0.96) and len(text) < 80:
            continue
        kept.append(block)
    return kept


def restore_reading_order(blocks: list[Block], page_width: float) -> list[Block]:
    if len(blocks) <= 1:
        return list(blocks)
    body = [block for block in blocks if block.type not in FIGURE_TYPES | TABLE_TYPES]
    media = [block for block in blocks if block.type in FIGURE_TYPES | TABLE_TYPES]
    if not body:
        return sorted(media, key=lambda item: (item.page, item.bbox[1], item.bbox[0]))
    centers = [(block.bbox[0] + block.bbox[2]) / 2 for block in body]
    left_count = sum(1 for center in centers if center < page_width * 0.48)
    right_count = sum(1 for center in centers if center > page_width * 0.52)
    if left_count >= 2 and right_count >= 2:
        left = sorted([block for block in body if (block.bbox[0] + block.bbox[2]) / 2 < page_width * 0.5], key=lambda item: (item.bbox[1], item.bbox[0]))
        right = sorted([block for block in body if (block.bbox[0] + block.bbox[2]) / 2 >= page_width * 0.5], key=lambda item: (item.bbox[1], item.bbox[0]))
        ordered = left + right
    else:
        ordered = sorted(body, key=lambda item: (item.bbox[1], item.bbox[0]))
    return sorted(media, key=lambda item: (item.bbox[1], item.bbox[0])) + ordered if media and not ordered else ordered + sorted(media, key=lambda item: (item.bbox[1], item.bbox[0]))


def crop_layout_assets(page_png: Path, blocks: list[Block], output_dir: Path, figures_dir: Path, tables_dir: Path) -> int:
    count = 0
    image = None
    for block in blocks:
        if block.type not in FIGURE_TYPES | TABLE_TYPES:
            continue
        image_bbox = block.meta.get("image_bbox")
        if not image_bbox:
            continue
        if image is None:
            image = Image.open(page_png)
        target_dir = tables_dir if block.type in TABLE_TYPES else figures_dir
        prefix = "table" if block.type in TABLE_TYPES else "figure"
        target = target_dir / f"{prefix}_{block.page:03d}_{count + 1:03d}.png"
        crop = image.crop(tuple(int(max(0, v)) for v in image_bbox))
        crop.save(target)
        block.asset_path = str(target.relative_to(output_dir))
        count += 1
    return count


def extract_pdf_image_blocks(page: fitz.Page, page_index: int, blocks: list[Block], output_dir: Path, figures_dir: Path) -> list[Block]:
    extracted: list[Block] = []
    page_dict = page.get_text("dict")
    for raw in page_dict.get("blocks", []):
        if raw.get("type") != 1 or not raw.get("image"):
            continue
        bbox = [float(v) for v in raw.get("bbox", [0, 0, 0, 0])]
        if not any(overlap_ratio(bbox, block.bbox) > 0.8 for block in blocks):
            continue
        ext = str(raw.get("ext") or "png")
        target = figures_dir / f"figure_{page_index:03d}_pdf_{len(extracted) + 1:03d}.{ext}"
        target.write_bytes(raw["image"])
        extracted.append(
            Block(
                id=f"p{page_index:03d}_pdfimg{len(extracted):03d}",
                page=page_index,
                type="figure",
                bbox=bbox,
                source="pdf_image",
                asset_path=str(target.relative_to(output_dir)),
            )
        )
    return extracted


def build_document_ir(blocks: list[Block]) -> list[Block]:
    content: list[Block] = []
    seen_text: set[str] = set()
    for block in blocks:
        if block.type in FIGURE_TYPES | TABLE_TYPES:
            if block.asset_path:
                content.append(block)
            continue
        text = normalize_text(block.text)
        if not text:
            continue
        fingerprint = re.sub(r"\s+", " ", text).strip().lower()
        if fingerprint in seen_text:
            continue
        seen_text.add(fingerprint)
        block.text = text
        block.level = heading_level(text, block.type)
        content.append(block)
    return content


def block_to_ir(block: Block, output_dir: Path) -> dict[str, Any]:
    item = asdict(block)
    if item.get("asset_path"):
        item["asset_path"] = str(Path(item["asset_path"]))
    return item


def render_markdown(document: dict[str, Any], output_dir: Path) -> str:
    lines = [
        "<!-- Generated by Bamboo local-pdf-to-markdown workflow. -->",
        f"<!-- Source: {document['metadata']['source']} -->",
        "",
    ]
    title_written = False
    for item in document.get("content", []):
        item_type = item.get("type", "text")
        text = str(item.get("text") or "").strip()
        asset_path = str(item.get("asset_path") or "").strip()
        if item_type in FIGURE_TYPES | TABLE_TYPES and asset_path:
            alt = "Table" if item_type in TABLE_TYPES else "Figure"
            lines.extend([f"![{alt}]({asset_path})", ""])
            continue
        if not text:
            continue
        level = int(item.get("level") or 0)
        if level:
            if level == 1 and title_written:
                level = 2
            if level == 1:
                title_written = True
            lines.extend([f"{'#' * level} {single_line(text)}", ""])
        else:
            paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
            for paragraph in paragraphs:
                lines.extend([paragraph.replace("\n", " "), ""])
    return "\n".join(lines).rstrip() + "\n"


def infer_text_type(text: str, font_size: float, page_height: float, bbox: list[float]) -> str:
    compact = single_line(text)
    if bbox[1] < page_height * 0.2 and font_size >= 15 and len(compact) < 240:
        return "title"
    if heading_level(compact, "text"):
        return "section_title"
    if re.match(r"^(fig(?:ure)?|table)\s*[\dIVXLC]+[.:]", compact, re.I):
        return "caption"
    return "text"


def heading_level(text: str, block_type: str) -> int | None:
    compact = single_line(text)
    if block_type == "title":
        return 1
    if re.match(r"^(abstract|introduction|methods?|materials|results|discussion|conclusion|references|acknowledgements?)\b", compact, re.I):
        return 2
    if re.match(r"^\d+\.\s+\S", compact):
        return 2
    if re.match(r"^\d+\.\d+\.?\s+\S", compact):
        return 3
    if re.match(r"^\d+\.\d+\.\d+\.?\s+\S", compact):
        return 4
    if block_type == "section_title" and len(compact) < 120:
        return 2
    return None


def map_layout_type(raw_type: str) -> str:
    value = raw_type.lower().replace(" ", "_").replace("-", "_")
    mapping = {
        "title": "title",
        "plain_text": "text",
        "text": "text",
        "abandon": "other",
        "figure": "figure",
        "figure_caption": "caption",
        "table": "table",
        "table_caption": "caption",
        "isolate_formula": "formula",
        "formula": "formula",
        "header": "header",
        "footer": "footer",
    }
    return mapping.get(value, value)


def overlap_ratio(a: list[float], b: list[float]) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area = max(1.0, (a[2] - a[0]) * (a[3] - a[1]))
    return inter / area


def normalize_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"-\n(?=[a-z])", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def single_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
