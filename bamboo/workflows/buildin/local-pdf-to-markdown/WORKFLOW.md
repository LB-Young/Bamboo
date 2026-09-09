---
name: local-pdf-to-markdown
description: Convert a local PDF file into a structured Markdown document with a retained JSON IR and extracted assets.
usage: |
  1. Call `workflow_load` with `name="local-pdf-to-markdown"` before running this workflow.
  2. Call `workflow_run` with `name="local-pdf-to-markdown"` and arguments containing a local PDF path.
  3. Arguments may be either `"/absolute/input.pdf"` or `"/absolute/input.pdf /absolute/output.md"`.
  4. The workflow returns the generated Markdown file path in stdout as `Markdown: ...`.
dependencies:
  - PyMuPDF
  - Pillow
  - Optional doclayout-yolo Python package for layout detection
  - Optional PaddleOCR / PP-OCRv5 for scanned pages
---

# Local PDF To Markdown Workflow

## 功能

将本地 PDF 文件转换为结构化 Markdown 文件。输入是一个本地 PDF 路径，输出是一个本地 `.md` 文件路径，同时保留中间结构化结果和资产文件，便于后续继续增强表格结构识别、公式识别、OCR 校正和 RAG 切分。

第一版优先保证：

- PDF 原生文字层优先，减少 OCR 对科学符号、公式、上标下标的破坏。
- 逐页渲染页面 PNG，保留调试材料。
- 可用 DocLayout-YOLO 时执行版面检测并裁剪 Figure/Table。
- 可用 OCR 时补充扫描页文本。
- 按页、栏、坐标恢复阅读顺序。
- 输出 `document.json` 作为 Document IR，再从 IR 渲染 Markdown。

## 使用方式

```json
{"name": "local-pdf-to-markdown", "arguments": "\"/Users/me/papers/demo.pdf\""}
```

或者显式指定输出 Markdown：

```json
{"name": "local-pdf-to-markdown", "arguments": "\"/Users/me/papers/demo.pdf\" \"/Users/me/papers/demo/demo.md\""}
```

如果只传入 PDF 路径，默认输出目录为 PDF 同级目录下的同名文件夹：

```text
demo/
├── demo.md
├── document.json
├── pages/
├── layout/
└── assets/
    ├── figures/
    └── tables/
```

## 执行流程

1. 校验输入 PDF 路径并创建输出目录。
2. 使用 PyMuPDF 打开 PDF，读取页面尺寸、原生文字块、字体大小、bbox 和图片块。
3. 以 `workflows_buildin.yaml` 配置的 DPI 渲染每一页到 `pages/page_XXX.png`。
4. 如果 `workflows_buildin.yaml` 中配置的 DocLayout-YOLO 权重存在且 `doclayout_yolo` 可导入，则对页面 PNG 进行版面分析，并保存 `layout/page_XXX.json`。
5. 如果页面没有可靠原生文字且 PaddleOCR 可用，则对页面执行 OCR 作为补充文本。
6. 使用几何规则做单栏/双栏阅读顺序恢复，过滤页眉页脚和页码。
7. 从版面检测结果或 PDF 图片块裁剪并保存 Figure/Table 资产。
8. 生成 `document.json`。
9. 从 Document IR 渲染 Markdown。

## 输出约定

运行成功后，stdout 会包含：

```text
Markdown: /absolute/path/to/output.md
IR: /absolute/path/to/document.json
OutputDir: /absolute/path/to/output-directory
```

最终回答用户时，优先返回 Markdown 文件路径；如用户需要调试，再返回 `document.json` 和 `pages/`、`layout/`、`assets/` 目录。

## 限制

- `run` 入口、超时、DPI、layout 模型路径、OCR 检测/识别模型名称、OCR 本地模型目录、设备和 OCR 开关集中配置在 `bamboo/configs/workflows_buildin.yaml`。
- 未安装 `doclayout-yolo` 或配置的模型权重不存在时，workflow 会降级为 PyMuPDF 原生文本结构化转换，仍会输出 Markdown 和 IR。
- 未安装 PaddleOCR 时，扫描 PDF 的 OCR 文本可能为空，但页面 PNG 会保留，方便后续补跑 OCR。
- 第一版表格以图片资产形式保留，不强制转换为 Markdown 表格。
- 第一版公式优先保留原生文本；无法可靠解析的公式区域可在后续模型增强中转为 LaTeX。
