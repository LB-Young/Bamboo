---
name: video-insight
description: Extract audio, speech transcript, keyframes, OCR text, keyframe descriptions, and visual summaries from a local video file.
usage: |
  1. Call `workflow_load` with `name="video-insight"` before running this workflow.
  2. Call `workflow_run` with `name="video-insight"` and arguments containing a local video path.
  3. By default, pass only the video path. Do not invent or pass an output directory. The workflow must create a child directory for the current video under `VIDEO_INSIGHT_OUTPUT_DIR`, or under `~/.bamboo/workspace/video-insight` when that variable is unset.
  4. Pass an explicit output directory only when the user explicitly requests a different location.
  5. Keep downstream artifacts derived from this video, such as article drafts and generated documents, under the `OutputDir` returned by this workflow.
  6. Extra process flags are supported, for example `--skip-transcript`, `--skip-vision`, `--skip-ocr`, `--device cuda`, or `--vision-model-dir /models/vision-language-model`.
  7. The workflow returns the output directory and key artifact paths in stdout.
dependencies:
- ffmpeg
- ffprobe
- faster-whisper (optional, for speech transcription)
- PaddleOCR / PaddlePaddle (optional, for keyframe OCR)
- torch / transformers / accelerate / qwen-vl-utils (optional, for local vision-language model analysis)
run:
  script: scripts/run_video_insight.py
  cwd: .
  timeout: 7200
  risk: write
---
# Video Insight Workflow

## 功能

将一个本地视频文件转换成一组可继续分析、写作或归档的副产品。它适合固定的“视频材料入库”流程：输入一个本地视频路径，输出音频、字幕文本、关键帧、OCR 文本、关键帧描述、画面总结和总报告。

这个 workflow 不负责下载视频。对于 Bilibili、抖音、小红书、YouTube、知乎等平台内容，先用对应 reach skill 下载到本地文件，再运行本 workflow。

## 使用方式

### 输出目录规则（必须遵循）

- 默认调用时只传视频路径，不得由 Agent 自行编造或附加输出目录。
- 使用 `.env` 中的 `VIDEO_INSIGHT_OUTPUT_DIR` 作为统一输出根目录。
- 未配置该变量时，统一使用 `~/.bamboo/workspace/video-insight/`。
- Workflow 会以当前视频文件名创建独立子目录，音频、字幕、关键帧、OCR、分析报告等文件全部保存在该子目录内。
- 后续基于该视频制作文章、报告或其他产物时，应继续保存在 Workflow 返回的 `OutputDir` 下，例如 `OutputDir/article/`，不得另行在 `~/.bamboo/workspace` 下创建同级临时目录。
- 只有用户明确要求其他保存位置时，才允许传入显式输出目录。

默认用法如下：

```json
{"name": "video-insight", "arguments": "\"/Users/me/videos/demo.mp4\""}
```

例如输入 `/Users/me/videos/demo.mp4` 时，默认输出目录通常是：

```text
/Users/me/.bamboo/workspace/video-insight/demo/
```

如果同名目录已存在，会自动使用 `demo-2/`、`demo-3/` 这类后缀，避免覆盖旧结果。

用户明确要求其他位置时，可以显式指定输出目录；显式目录优先级最高，会绕过默认输出根目录：

```json
{"name": "video-insight", "arguments": "\"/Users/me/videos/demo.mp4\" \"/Users/me/outputs/demo-video\""}
```

跳过耗时或未配置的能力：

```json
{"name": "video-insight", "arguments": "\"/Users/me/videos/demo.mp4\" --skip-transcript --skip-vision"}
```

指定本地模型路径：

```json
{"name": "video-insight", "arguments": "\"/Users/me/videos/demo.mp4\" --model-dir \"/models/whisper\" --vision-model-dir \"/models/vision-language-model\" --device cuda"}
```

> 由于 Bamboo 当前 `workflow_run` 将参数作为一个字符串传给脚本，路径包含空格时请使用 shell 风格引号。

## 环境变量

脚本直接运行时会读取 `~/.bamboo/.env` 和 `~/.Bamboo/.env`。

```bash
# 提取结果输出根目录；每个视频会在这个目录下面自动创建一个独立子目录。
# 未配置时默认使用 ~/.bamboo/workspace/video-insight。
VIDEO_INSIGHT_OUTPUT_DIR=/absolute/path/to/video-insight-output

# faster-whisper 模型目录；包含 model.bin 时直接加载本地模型，否则作为指定下载目录。
VIDEO_INSIGHT_MODEL_DIR=/absolute/path/to/video-insight-models

# 本地多模态模型目录；用于关键帧描述和整体画面总结。
# 需要是当前 transformers 支持的 image-text-to-text 模型。
VIDEO_INSIGHT_VISION_MODEL_DIR=/absolute/path/to/vision-language-model

# 视觉模型运行设备；auto 在 Apple Silicon 上选 MPS，其他环境自动分配，也可指定 mps/cuda/cpu。
VIDEO_INSIGHT_VISION_DEVICE=auto

# 视觉模型权重 dtype；auto 通常即可，也可按环境改成 float16/bfloat16。
VIDEO_INSIGHT_VISION_DTYPE=auto

# 单帧描述最大 token 数；整段画面总结使用至少 512 token 的上限。
VIDEO_INSIGHT_VISION_MAX_NEW_TOKENS=512

# 最多送入视觉模型分析的关键帧数量，避免长视频一次处理太多图片。
VIDEO_INSIGHT_MAX_VISION_FRAMES=12

# 输出语言，默认中文。
VIDEO_INSIGHT_ANALYSIS_LANGUAGE=zh-CN

# 是否启用关键帧 OCR；auto 表示能加载 PaddleOCR 就使用，disabled/false/off 可关闭。
VIDEO_INSIGHT_ENABLE_OCR=auto
VIDEO_INSIGHT_OCR_DEVICE=auto

# PaddleOCR 检测模型名称和本地目录，用于定位画面中文字区域。
VIDEO_INSIGHT_OCR_DETECTION_MODEL_NAME=PP-OCRv5_mobile_det
VIDEO_INSIGHT_OCR_DETECTION_MODEL_DIR=/absolute/path/to/PP-OCRv5_mobile_det

# PaddleOCR 识别模型名称和本地目录，用于把检测到的文字区域识别成文本。
VIDEO_INSIGHT_OCR_RECOGNITION_MODEL_NAME=PP-OCRv5_mobile_rec
VIDEO_INSIGHT_OCR_RECOGNITION_MODEL_DIR=/absolute/path/to/PP-OCRv5_mobile_rec
```

## 执行流程

1. 校验本地视频路径并创建输出目录。
2. 使用 `ffmpeg` 抽取 `audio.wav`。
3. 如果未传 `--skip-transcript`，使用 `faster-whisper` 生成 `transcript.json`、`transcript.srt`、`transcript.vtt`。
4. 使用 `ffmpeg` 场景检测抽取关键帧到 `keyframes/`，并生成 `keyframes.json`；场景帧少于两张时每 10 秒抽帧，时间戳取自视频实际帧；短视频至少兜底抽首帧。
5. 如果未传 `--skip-vision`，在整段视频的关键帧中均匀选取最多 12 张，运行 OCR、关键帧描述和整体画面总结，生成 `keyframe_analysis.json`。
6. 生成 `report.json` 汇总所有副产品路径和运行结果。

## 输出约定

运行成功后，stdout 会包含：

```text
OutputDir: /absolute/path/to/output-directory
Report: /absolute/path/to/output-directory/report.json
Audio: /absolute/path/to/output-directory/audio.wav
Keyframes: /absolute/path/to/output-directory/keyframes
KeyframesJson: /absolute/path/to/output-directory/keyframes.json
KeyframeAnalysis: /absolute/path/to/output-directory/keyframe_analysis.json
TranscriptJson: /absolute/path/to/output-directory/transcript.json
TranscriptSrt: /absolute/path/to/output-directory/transcript.srt
TranscriptVtt: /absolute/path/to/output-directory/transcript.vtt
```

最终回答用户时，优先返回 `OutputDir` 和 `Report`。如果用户要继续写文章或做二次分析，再返回字幕、关键帧和画面分析文件。

## 限制

- 语音转写的 `--device auto` 自动选择 CUDA 或 CPU；`--compute-type auto` 对应 float16 或 int8。视觉模型的 `auto` 按 CUDA、MPS、CPU 的顺序选择设备，CUDA 可用时由 Transformers 自动分配 GPU。OCR 的 `VIDEO_INSIGHT_OCR_DEVICE=auto` 在 GPU 版 Paddle 可用时选择 `gpu:0`，否则回退 CPU。Apple Silicon 的语音转写使用 CPU，视觉分析可使用 MPS。
- 未指定语音模型目录时会报错，不会隐式下载到默认缓存目录。
- 视觉分析使用本地多模态模型目录，脚本通过 transformers auto class 以 `local_files_only=True` 加载，不会联网下载模型。
- 未配置 `VIDEO_INSIGHT_VISION_MODEL_DIR` 时，基础音频和关键帧仍会产出，报告中会记录视觉分析错误。
- 未安装 `faster-whisper` 时，语音转写不可用；可以传 `--skip-transcript` 只生成音频和关键帧。
- 未安装 PaddleOCR 时，OCR 文本为空，但视觉描述仍可在配置视觉模型后运行。
