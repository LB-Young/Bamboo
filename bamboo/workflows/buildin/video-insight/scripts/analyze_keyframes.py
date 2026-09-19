#!/usr/bin/env python3
"""Describe keyframes, run OCR, and summarize visuals with local models only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    parser = argparse.ArgumentParser(description="Analyze extracted video keyframes with local OCR and local vision-language models.")
    parser.add_argument("--keyframes-json")
    parser.add_argument("--keyframes-dir")
    parser.add_argument("--output", required=True)
    parser.add_argument("--vision-model-dir", default=os.environ.get("VIDEO_INSIGHT_VISION_MODEL_DIR", ""))
    parser.add_argument("--vision-device", default=os.environ.get("VIDEO_INSIGHT_VISION_DEVICE", "auto"))
    parser.add_argument("--vision-dtype", default=os.environ.get("VIDEO_INSIGHT_VISION_DTYPE", "auto"))
    parser.add_argument("--max-new-tokens", type=int, default=int(os.environ.get("VIDEO_INSIGHT_VISION_MAX_NEW_TOKENS", "512")))
    parser.add_argument("--skip-ocr", action="store_true")
    parser.add_argument("--skip-description", action="store_true")
    parser.add_argument("--max-frames", type=int, default=int(os.environ.get("VIDEO_INSIGHT_MAX_VISION_FRAMES", "12")))
    parser.add_argument("--language", default=os.environ.get("VIDEO_INSIGHT_ANALYSIS_LANGUAGE", "zh-CN"))
    args = parser.parse_args(argv)

    try:
        result = analyze_keyframes(args)
    except RuntimeError as exc:
        print(f"Video insight error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def analyze_keyframes(args: argparse.Namespace) -> dict[str, Any]:
    frames = load_frame_entries(args.keyframes_json, args.keyframes_dir)
    if 0 < args.max_frames < len(frames):
        if args.max_frames == 1:
            frames = [frames[len(frames) // 2]]
        else:
            frames = [frames[round(i * (len(frames) - 1) / (args.max_frames - 1))] for i in range(args.max_frames)]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ocr_engine, ocr_warning = (None, "")
    if not args.skip_ocr:
        ocr_engine, ocr_warning = load_ocr_engine()

    vision_model = None
    vision_model_dir = ""
    if not args.skip_description:
        vision_model_dir = resolve_required_dir(args.vision_model_dir, "VIDEO_INSIGHT_VISION_MODEL_DIR")
        vision_model = LocalVisionLanguageModel(
            Path(vision_model_dir),
            device=args.vision_device,
            dtype=args.vision_dtype,
            max_new_tokens=args.max_new_tokens,
        )

    analyzed_frames = []
    for frame in frames:
        image_path = Path(str(frame["path"])).expanduser()
        item = dict(frame)
        item["path"] = str(image_path)
        item["ocr_text"] = "" if args.skip_ocr else run_ocr(ocr_engine, image_path)
        item["description"] = ""
        if vision_model is not None:
            item["description"] = describe_frame(vision_model, image_path, frame=item, language=args.language)
        analyzed_frames.append(item)

    visual_summary = ""
    if vision_model is not None and analyzed_frames:
        visual_summary = summarize_visuals(vision_model, analyzed_frames, language=args.language)

    data = {
        "vision_model_dir": vision_model_dir or None,
        "ocr_enabled": not args.skip_ocr and ocr_engine is not None,
        "ocr_warning": ocr_warning,
        "frames": analyzed_frames,
        "visual_summary": visual_summary,
    }
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_env_file() -> None:
    for path in (Path.home() / ".bamboo" / ".env", Path.home() / ".Bamboo" / ".env"):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            parsed = parse_env_line(raw_line)
            if parsed is None:
                continue
            key, value = parsed
            os.environ.setdefault(key, value)


def parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].lstrip()
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


class LocalVisionLanguageModel:
    """Lazy local vision-language runner based on transformers auto classes."""

    def __init__(self, model_dir: Path, *, device: str, dtype: str, max_new_tokens: int) -> None:
        if not model_dir.is_dir():
            raise RuntimeError(f"vision model directory not found: {model_dir}")
        try:
            import torch
            from qwen_vl_utils import process_vision_info
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except ImportError as exc:
            raise RuntimeError(
                "missing local vision dependencies: install torch, transformers, accelerate, and qwen-vl-utils"
            ) from exc

        self.torch = torch
        self.process_vision_info = process_vision_info
        self.max_new_tokens = max_new_tokens
        if device == "auto" and torch.backends.mps.is_available():
            device = "mps"
        device_map: str | None = "auto" if device == "auto" else None
        kwargs: dict[str, Any] = {
            "dtype": resolve_torch_dtype(torch, dtype),
            "local_files_only": True,
        }
        if device_map:
            kwargs["device_map"] = device_map
        try:
            self.model = AutoModelForImageTextToText.from_pretrained(str(model_dir), **kwargs)
        except ValueError as exc:
            raise RuntimeError(
                f"unsupported vision-language model at {model_dir}; update transformers or use a supported model"
            ) from exc
        if not device_map:
            self.model.to(device)
        self.processor = AutoProcessor.from_pretrained(
            str(model_dir), local_files_only=True, max_pixels=512 * 28 * 28,
        )

    def generate(self, prompt: str, *, image_path: Path | None = None, max_new_tokens: int | None = None) -> str:
        content: list[dict[str, Any]] = []
        if image_path is not None:
            content.append({"type": "image", "image": str(image_path)})
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = self.process_vision_info(messages)
        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to(next(self.model.parameters()).device)
        with self.torch.inference_mode():
            generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens or self.max_new_tokens, do_sample=False)
        generated_trimmed = [
            output_ids[len(input_ids) :]
            for input_ids, output_ids in zip(inputs.input_ids, generated_ids, strict=False)
        ]
        decoded = self.processor.batch_decode(generated_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        return (decoded[0] if decoded else "").strip()


def resolve_torch_dtype(torch: Any, dtype: str) -> Any:
    value = str(dtype or "auto").strip().lower()
    if value == "auto":
        return "auto"
    aliases = {
        "float16": torch.float16,
        "fp16": torch.float16,
        "half": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }
    if value not in aliases:
        raise RuntimeError(f"unsupported VIDEO_INSIGHT_VISION_DTYPE: {dtype}")
    return aliases[value]


def resolve_required_dir(value: str, env_name: str) -> str:
    path_value = str(value or "").strip()
    if not path_value:
        raise RuntimeError(f"{env_name} is required for keyframe description and visual summary")
    path = Path(path_value).expanduser()
    if not path.is_dir():
        raise RuntimeError(f"{env_name} directory not found: {path}")
    return str(path.resolve())


def load_frame_entries(keyframes_json: str | None, keyframes_dir: str | None) -> list[dict[str, Any]]:
    if keyframes_json:
        path = Path(keyframes_json).expanduser()
        if not path.is_file():
            raise RuntimeError(f"keyframes json not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        frames = data.get("frames") if isinstance(data, dict) else None
        if not isinstance(frames, list):
            raise RuntimeError(f"keyframes json does not contain frames: {path}")
        return [frame for frame in frames if isinstance(frame, dict) and frame.get("path")]
    if keyframes_dir:
        directory = Path(keyframes_dir).expanduser()
        if not directory.is_dir():
            raise RuntimeError(f"keyframes directory not found: {directory}")
        return [
            {"index": index, "time": None, "path": str(path), "method": "directory"}
            for index, path in enumerate(sorted(directory.glob("*.jpg")), start=1)
        ]
    raise RuntimeError("--keyframes-json or --keyframes-dir is required")


def load_ocr_engine() -> tuple[Any | None, str]:
    enable_ocr = os.environ.get("VIDEO_INSIGHT_ENABLE_OCR", "auto").strip().lower()
    if enable_ocr in {"0", "false", "no", "off", "disabled"}:
        return None, "OCR is disabled by VIDEO_INSIGHT_ENABLE_OCR."
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError:
        return None, "PaddleOCR is not installed; keyframe OCR is skipped."

    kwargs: dict[str, Any] = {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
    }
    detection_name = env_value("VIDEO_INSIGHT_OCR_DETECTION_MODEL_NAME")
    recognition_name = env_value("VIDEO_INSIGHT_OCR_RECOGNITION_MODEL_NAME")
    detection_dir = configured_model_dir(env_value("VIDEO_INSIGHT_OCR_DETECTION_MODEL_DIR"))
    recognition_dir = configured_model_dir(env_value("VIDEO_INSIGHT_OCR_RECOGNITION_MODEL_DIR"))
    if not detection_dir or not recognition_dir:
        return None, "Set both VIDEO_INSIGHT_OCR model directories; default model downloads are disabled."
    if detection_name:
        kwargs["text_detection_model_name"] = detection_name
    if detection_dir:
        kwargs["text_detection_model_dir"] = str(detection_dir)
    if recognition_name:
        kwargs["text_recognition_model_name"] = recognition_name
    if recognition_dir:
        kwargs["text_recognition_model_dir"] = str(recognition_dir)

    try:
        return PaddleOCR(**kwargs), ""
    except Exception as exc:
        return None, f"PaddleOCR failed to initialize: {exc}"


def env_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def configured_model_dir(value: str) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
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


def normalize_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip())


def describe_frame(model: LocalVisionLanguageModel, image_path: Path, *, frame: dict[str, Any], language: str) -> str:
    prompt = (
        f"请用{language}描述这张视频关键帧。"
        "输出一段简洁但信息密集的描述，包含主体、场景、屏幕文字、动作/状态、可能的业务含义。"
        f"关键帧序号: {frame.get('index')}；时间戳: {frame.get('time')}。"
    )
    return model.generate(prompt, image_path=image_path)


def summarize_visuals(model: LocalVisionLanguageModel, frames: list[dict[str, Any]], *, language: str) -> str:
    frame_lines = []
    for frame in frames:
        frame_lines.append(
            "\n".join(
                [
                    f"帧 {frame.get('index')} 时间 {frame.get('time')}:",
                    f"OCR: {frame.get('ocr_text') or '(无)'}",
                    f"描述: {frame.get('description') or '(无)'}",
                ]
            )
        )
    prompt = (
        f"请用{language}根据下面的视频关键帧 OCR 和描述，总结视频画面内容。"
        "请输出：1. 画面主线；2. 关键视觉证据；3. 屏幕文字/字幕线索；4. 不确定点。"
        "每项一到两句话，总长度不超过300个中文字符。不要推断画面中没有依据的内容。"
        "\n\n"
        + "\n\n".join(frame_lines)
    )
    return model.generate(prompt, max_new_tokens=max(512, model.max_new_tokens))


if __name__ == "__main__":
    raise SystemExit(main())
