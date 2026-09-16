---
name: video-insight
description: Extract speech transcripts, keyframes, OCR text, visual descriptions, and visual summaries from local video files.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - video
      - audio
      - transcription
      - keyframes
      - local
---

# Video Insight

## When to Use

Use this skill when the task needs to analyze a local video file by extracting speech text, timestamped transcript segments, subtitles, keyframe images, OCR text, keyframe descriptions, or visual summaries.

Do not use this skill to download videos from websites. Use the platform reach skills for RedFoxHub download APIs first, then run this skill on the resulting local media file.

## Requirements

Required:

```bash
ffmpeg -version
ffprobe -version
```

Optional for speech transcription:

```bash
python -c "import faster_whisper"
```

For NVIDIA GPU transcription, install a CUDA-capable `faster-whisper` / CTranslate2 environment and pass `--device cuda`.

Set `VIDEO_INSIGHT_MODEL_DIR` to control where faster-whisper stores or reads model files. This avoids downloading models into the default cache directory.

```bash
# faster-whisper 模型目录；提前下载好的 Whisper 模型放这里，也会作为下载目录使用。
VIDEO_INSIGHT_MODEL_DIR=/absolute/path/to/video-insight-models
```

The scripts load environment variables from `~/.bamboo/.env` and `~/.Bamboo/.env` when run directly.

Optional for keyframe OCR:

```bash
python -c "import paddleocr"
```

Keyframe description and visual summary use a local Qwen2.5-VL-compatible model loaded directly by the script. Set `VIDEO_INSIGHT_VISION_MODEL_DIR` to an already-downloaded local model directory. The script uses `local_files_only=True`, so it will not download model files into default cache locations.

```bash
# 本地 Qwen2.5-VL 模型目录；用于关键帧描述和整体画面总结。
VIDEO_INSIGHT_VISION_MODEL_DIR=/absolute/path/to/Qwen2.5-VL-model

# 视觉模型运行设备；auto 让 transformers/accelerate 自动分配，cuda/cpu 可手动指定。
VIDEO_INSIGHT_VISION_DEVICE=auto

# 视觉模型权重 dtype；auto 通常即可，也可按环境改成 float16/bfloat16。
VIDEO_INSIGHT_VISION_DTYPE=auto

# 每次视觉模型生成的最大 token 数，影响关键帧描述和画面总结长度。
VIDEO_INSIGHT_VISION_MAX_NEW_TOKENS=512
```

Required Python packages for local visual description:

```bash
python -c "import torch, transformers, qwen_vl_utils"
```

OCR uses the same PaddleOCR style as the `local-pdf-to-markdown` workflow. Configure these variables if you keep PP-OCRv5 in custom paths:

```bash
# 是否启用关键帧 OCR；auto 表示能加载 PaddleOCR 就使用，disabled/false/off 可关闭。
VIDEO_INSIGHT_ENABLE_OCR=auto

# PaddleOCR 检测模型名称和本地目录，用于定位画面中文字区域。
VIDEO_INSIGHT_OCR_DETECTION_MODEL_NAME=PP-OCRv5_mobile_det
VIDEO_INSIGHT_OCR_DETECTION_MODEL_DIR=/absolute/path/to/PP-OCRv5_mobile_det

# PaddleOCR 识别模型名称和本地目录，用于把检测到的文字区域识别成文本。
VIDEO_INSIGHT_OCR_RECOGNITION_MODEL_NAME=PP-OCRv5_mobile_rec
VIDEO_INSIGHT_OCR_RECOGNITION_MODEL_DIR=/absolute/path/to/PP-OCRv5_mobile_rec
```

## Scripts

```bash
python <skill_dir>/scripts/extract_audio.py ./input.mp4 --output ./outputs/audio.wav
python <skill_dir>/scripts/transcribe_audio.py ./outputs/audio.wav --output-dir ./outputs --model large-v3 --model-dir /absolute/path/to/video-insight-models --device cuda
python <skill_dir>/scripts/extract_keyframes.py ./input.mp4 --output-dir ./outputs/keyframes --scene-threshold 0.35
python <skill_dir>/scripts/analyze_keyframes.py --keyframes-json ./outputs/keyframes.json --output ./outputs/keyframe_analysis.json --vision-model-dir /absolute/path/to/Qwen2.5-VL-model
python <skill_dir>/scripts/process_video.py ./input.mp4 --output-dir ./outputs --model large-v3 --model-dir /absolute/path/to/video-insight-models --device cuda --vision-model-dir /absolute/path/to/Qwen2.5-VL-model
```

## Outputs

`process_video.py` creates:

- `audio.wav`
- `transcript.json`
- `transcript.srt`
- `transcript.vtt`
- `keyframes/`
- `keyframes.json`
- `keyframe_analysis.json`
- `report.json`

Use `--skip-vision` to skip keyframe description and visual summary. Use `--skip-ocr` to skip PaddleOCR while still using the vision model.

## Local GPU Guidance

For two 16 GB NVIDIA GPUs, prefer task parallelism over model sharding: run faster-whisper on one GPU and reserve the other GPU for future visual-language keyframe description or another video job.
