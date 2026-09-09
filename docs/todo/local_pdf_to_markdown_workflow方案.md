# 本地 PDF → 结构化 Markdown 转换 Workflow 方案

## 1. 项目目标

构建一套可完全在本地运行的 PDF 文档解析 Workflow，将用户输入的 PDF 文件转换为结构化 Markdown（`.md`）文件。

系统重点面向学术论文、技术报告等具有复杂版面的文档，需要完成：

- PDF 页面解析与渲染
- 数字 PDF / 扫描 PDF 判断
- 文档版面分析
- 正文与标题文本提取
- OCR 文字识别
- 多栏阅读顺序恢复
- 标题层级恢复
- 图片检测、裁剪与保存
- 表格检测、裁剪与保存
- Figure/Table Caption 关联
- 页眉、页脚、页码等无关内容过滤
- 最终按照文章逻辑结构生成 Markdown
- 保留中间结构化结果，便于后续扩展表格结构识别、公式识别和 LLM 校正

核心原则是：

> 优先使用 PDF 原生文字层保证科学文本准确性；OCR 作为扫描件和异常区域的补充；版面模型负责理解“哪里是什么”，Markdown Builder 负责恢复“文章应该如何组织”。

---

## 2. 总体技术路线

```text
                    User PDF
                       │
                       ▼
                ┌─────────────┐
                │ PDF Loader  │
                │   PyMuPDF   │
                └──────┬──────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
    PDF Text Layer             Page Rendering
          │                         │
          │                         ▼
          │                  Layout Analysis
          │                  DocLayout-YOLO
          │                         │
          │                         ▼
          │                   Layout Blocks
          │                         │
          └────────────┬────────────┘
                       ▼
                Block Processor
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
     Text            Figure           Table
       │               │                │
       ▼               ▼                ▼
 Native Text /       Crop &           Crop &
 PP-OCRv5            Save             Save
       │
       ▼
 Reading Order + Caption Association
                       │
                       ▼
              Document Structure
                       │
                       ▼
                Markdown Builder
                       │
                       ▼
                  output.md
```

---

## 3. 推荐模型与组件

### 3.1 PDF 基础解析：PyMuPDF

用途：

- 打开 PDF
- 获取页数、页面尺寸等基础信息
- 获取 PDF 原生文字层
- 获取文字块及其坐标
- 将 PDF 页面渲染为图片
- 为后续版面模型建立 PDF 坐标与图像坐标之间的映射

建议优先读取 PDF 原生文本，而不是对所有 PDF 页面直接 OCR。

原因是学术论文中经常包含：

- μ、α、β 等希腊字母
- 上标/下标
- 化学式
- 特殊单位
- 数学符号
- DOI
- 作者姓名和参考文献

原生 PDF text layer 通常比 OCR 更可靠。

---

### 3.2 版面分析首选：DocLayout-YOLO

**推荐等级：★★★★★**

主要任务：

- 检测 Title
- Section Header
- Text
- Figure
- Figure Caption
- Table
- Table Caption
- Formula 等文档元素
- 返回各元素类别、置信度和 Bounding Box

输入：

```text
page_001.png
```

输出示意：

```json
[
  {
    "type": "title",
    "bbox": [120, 80, 1800, 220],
    "score": 0.98
  },
  {
    "type": "text",
    "bbox": [120, 300, 900, 1000],
    "score": 0.96
  },
  {
    "type": "figure",
    "bbox": [950, 350, 1800, 1050],
    "score": 0.97
  }
]
```

### 选择原因

DocLayout-YOLO 属于针对文档版面优化的轻量检测方案，适合本地运行。与大型视觉语言模型相比，其计算资源和显存需求明显更低，也更容易进行批量 PDF 处理。

第一版 Workflow 建议优先使用：

```text
DocLayout-YOLO
```

如果后期发现复杂双栏论文的阅读顺序、标题类型区分等能力不足，可以进一步评估：

```text
PP-DocLayoutV2
```

作为替代或增强模型。

### License 注意事项

在科研、本地实验和未来产品化之前，需要分别检查模型权重、代码仓库及依赖组件的许可证。特别是准备闭源商业部署时，不应只依据模型“开源”这一点判断是否可直接商用。

---

## 4. OCR 模型：PP-OCRv5 Mobile

**推荐等级：★★★★★**

建议使用 PaddleOCR 的轻量 Mobile 系列。

OCR Pipeline：

```text
Image
  │
  ▼
Text Detection
  │
  ▼
Text Recognition
  │
  ▼
Text + Coordinates + Confidence
```

主要用于：

1. 扫描 PDF；
2. 图片型 PDF；
3. PDF 原生文字层缺失区域；
4. 原生文字解析异常的文本块；
5. 必要时对 Figure/Table 内部文字进行辅助识别。

### 不建议所有 PDF 都强制 OCR

推荐逻辑：

```python
if native_text_is_available:
    use_native_pdf_text()
else:
    use_ocr()
```

这样可以降低 OCR 对科学符号造成的错误，例如：

```text
μM     → uM
Co₃O₄  → Co3O4
10⁻³   → 10-3
α      → a
```

因此：

> OCR 应作为补充识别路径，而不是数字学术 PDF 的唯一文本来源。

---

## 5. PDF 类型判断

系统首先判断输入 PDF 是否存在可靠文字层。

### Digital PDF

特点：

- 可以直接选中文字；
- PyMuPDF 可以提取大量文本；
- 文字坐标信息完整。

处理：

```text
Native PDF Text
+
Layout Model
```

### Scanned PDF

特点：

- 页面本质为图片；
- 原生文字数量极少或不存在。

处理：

```text
Page Image
+
Layout Model
+
PP-OCRv5
```

### Mixed PDF

实际文档中还可能出现混合情况：

- 大部分页面有文字层；
- 少数页面为扫描件；
- 某些图注或嵌入对象无法正常提取。

因此最好采用**逐页甚至逐块判断**，而不是仅对整个 PDF 做一次二分类。

---

## 6. 页面渲染

建议：

```text
150–200 DPI
```

用于版面分析。

如果 OCR 小字识别效果不足，可以针对待 OCR 的局部区域使用更高分辨率重新渲染，而不是将整篇 PDF 全部以超高 DPI 处理。

建议输出：

```text
workspace/
└── pages/
    ├── page_001.png
    ├── page_002.png
    └── page_003.png
```

需要记录：

```text
PDF coordinate
↕
Rendered image coordinate
```

之间的缩放比例，以便把版面模型输出的 bbox 与 PDF 原生文字坐标对应。

---

## 7. 版面分析

每页图片进入：

```text
DocLayout-YOLO
```

生成：

```text
layout/page_001.json
layout/page_002.json
...
```

建议统一 Block Schema：

```json
{
  "id": "p001_b003",
  "page": 1,
  "type": "text",
  "bbox": [120, 320, 920, 980],
  "score": 0.967,
  "text": null,
  "source": null
}
```

建议至少支持以下逻辑类别：

```text
document_title
section_title
text
figure
figure_caption
table
table_caption
formula
header
footer
page_number
reference
other
```

不同模型原始类别可以通过 Mapping Layer 转换为上述统一类别，避免后续 Workflow 与某个特定模型强绑定。

---

## 8. 文本提取策略

对于每一个 Text Block：

### Step 1：寻找 PDF 原生文本

判断 PDF text bbox 是否与 layout bbox 相交。

例如：

```text
IoU / overlap > threshold
```

则提取对应 PDF 原生文字。

### Step 2：原生文字不可用

调用：

```text
PP-OCRv5
```

识别该区域。

### Step 3：保存文本来源

建议记录：

```json
{
  "text": "Electrochemical characterization...",
  "source": "native_pdf"
}
```

或者：

```json
{
  "text": "Electrochemical characterization...",
  "source": "ocr",
  "ocr_confidence": 0.96
}
```

这样后续可以针对低置信度 OCR 内容进行二次处理。

---

## 9. 阅读顺序恢复

这是 PDF → Markdown 中非常关键的一步。

论文经常是：

```text
┌───────────┬───────────┐
│ Left 1    │ Right 1   │
│ Left 2    │ Right 2   │
│ Left 3    │ Right 3   │
└───────────┴───────────┘
```

不能简单按照：

```python
sorted(blocks, key=lambda x: x.y)
```

排序。

否则可能变成：

```text
Left 1
Right 1
Left 2
Right 2
```

而真实阅读顺序应该是：

```text
Left 1
Left 2
Left 3
Right 1
Right 2
Right 3
```

### 第一版方法

采用：

```text
column detection
+
bbox geometry
+
top-to-bottom sorting
```

步骤：

1. 判断页面为单栏还是双栏/多栏；
2. 将 block 分配到对应 column；
3. column 内按照 y 坐标排序；
4. 处理跨栏 title / figure / table；
5. 生成最终 reading order。

### 后期增强

如果复杂页面的规则算法表现不够好，可使用带 Reading Order Prediction 的文档模型，例如 PP-DocLayoutV2。

---

## 10. 标题层级恢复

目标：

```markdown
# Paper Title

## Abstract

## 1. Introduction

## 2. Experimental

### 2.1 Materials

### 2.2 Characterization

## 3. Results and Discussion
```

标题层级可以综合以下信息：

```text
layout class
font size
font weight
numbering pattern
bbox position
text pattern
```

优先识别编号：

```regex
1.
2.
2.1
2.1.1
I.
II.
A.
B.
```

例如：

```text
2. Experimental Section
```

转换为：

```markdown
## 2. Experimental Section
```

而：

```text
2.1 Materials
```

转换为：

```markdown
### 2.1 Materials
```

对于没有编号的：

```text
Abstract
Introduction
Methods
Results
Discussion
Conclusion
References
```

可以通过规则库进行判断。

---

## 11. Figure 提取

版面模型检测到：

```text
figure
```

之后：

1. 获取 bbox；
2. 从高质量 page image 中裁剪；
3. 保存 PNG/JPEG；
4. 查找附近 Figure Caption；
5. 建立 Figure-Caption Association。

文件：

```text
assets/
└── figures/
    ├── figure_001.png
    ├── figure_002.png
    └── figure_003.png
```

Markdown：

```markdown
![Figure 1](assets/figures/figure_001.png)

**Figure 1.** Schematic illustration of the proposed sensing platform.
```

### Caption 关联

可结合：

```text
空间距离
+
上下位置
+
Figure/Fig. 文本关键词
```

例如：

```text
Figure bbox
↓
寻找下方最近 caption
↓
检测文本是否以 Fig. / Figure 开头
↓
建立关联
```

---

## 12. Table 提取

### 第一阶段推荐方案

不要一开始就做复杂 Table Structure Recognition。

先实现：

```text
Table Detection
↓
Crop
↓
Save Image
↓
Caption Association
↓
Insert Markdown
```

例如：

```markdown
![Table 1](assets/tables/table_001.png)

**Table 1.** Comparison of sensing performance.
```

优点：

- 实现简单；
- 表格内容不会因为错误解析而丢失；
- 合并单元格和复杂 scientific table 不会破坏；
- 适合作为 MVP。

---

## 13. Table Structure Recognition：第二阶段

后期增加：

```text
Table Image
     │
     ▼
Table Structure Recognition
     │
     ▼
Rows / Columns / Cells
     │
     ▼
HTML
     │
     ▼
Markdown Table
```

简单表格：

```markdown
| Sample | Sensitivity | LOD |
|---|---:|---:|
| A | 19.2 | 1.5 |
| B | 25.1 | 0.8 |
```

对于复杂合并单元格，建议保留 HTML：

```html
<table>
...
</table>
```

因为 Markdown 原生 Table 无法完整表达：

```text
rowspan
colspan
```

---

## 14. 公式处理

公式建议作为独立模块：

```text
Layout Model
      │
      ▼
Formula Detection
      │
      ▼
Formula Recognition
      │
      ▼
LaTeX
```

目标：

```markdown
$$
I_p = 2.69 \times 10^5 n^{3/2} A D^{1/2} C v^{1/2}
$$
```

而不是使用普通 OCR 输出公式。

### 第一版

可以：

```text
公式区域 → crop → image
```

或者优先保留 PDF 可提取字符。

### 第二版

再增加专门的 Formula → LaTeX 模型。

这样不会因为公式模块影响第一版 PDF → MD Workflow 的开发速度。

---

## 15. Header / Footer / Page Number 过滤

PDF 中经常出现：

```text
Journal Name
DOI
Downloaded by...
Page 3 of 12
© 2026 Elsevier...
```

这些不应该进入正文 Markdown。

过滤依据：

```text
layout class
+
page position
+
cross-page repetition
```

例如：

如果某段文本：

- 连续出现在大量页面；
- bbox 总是在页面顶部 5%；

则可以判断为：

```text
header
```

同理处理 footer/page number。

---

## 16. Document Intermediate Representation

不要从 Layout/OCR 直接生成 Markdown。

建议中间增加：

```text
Document IR
```

即统一文档结构 JSON。

示例：

```json
{
  "metadata": {
    "source": "paper.pdf",
    "pages": 12
  },
  "content": [
    {
      "type": "title",
      "level": 1,
      "text": "Wearable Electrochemical Sensors"
    },
    {
      "type": "section",
      "level": 2,
      "text": "1. Introduction"
    },
    {
      "type": "paragraph",
      "text": "Wearable sensors have attracted..."
    },
    {
      "type": "figure",
      "path": "assets/figures/figure_001.png",
      "caption": "Figure 1. Schematic illustration..."
    }
  ]
}
```

这一步非常重要。

系统应该是：

```text
PDF
 ↓
Layout/OCR
 ↓
Document IR
 ↓
Markdown
```

而不是：

```text
PDF
 ↓
直接拼 Markdown
```

这样未来可以非常容易增加：

```text
HTML Export
DOCX Export
JSON Export
RAG Chunking
LLM Processing
Knowledge Base
```

---

## 17. Markdown Builder

Markdown Builder 只负责：

```text
Document IR
→
Markdown
```

Mapping：

```text
document_title → #
section level 1 → ##
section level 2 → ###
paragraph → plain text
figure → ![]()
table → Markdown / HTML / image
formula → $$...$$
```

例如最终：

```markdown
# Wearable Electrochemical Sensors

## Abstract

Wearable electrochemical sensors have attracted considerable attention...

## 1. Introduction

Recent advances in flexible electronics...

![Figure 1](assets/figures/figure_001.png)

**Figure 1.** Schematic illustration of the sensing system.

## 2. Experimental Section

### 2.1 Materials

MXene was synthesized using...

### 2.2 Characterization

The morphology was characterized using...
```

---

## 18. 推荐工程目录

```text
pdf2md/
│
├── app.py
├── config.yaml
├── requirements.txt
│
├── models/
│   ├── layout/
│   └── ocr/
│
├── src/
│   ├── pdf/
│   │   ├── loader.py
│   │   ├── renderer.py
│   │   └── text_extractor.py
│   │
│   ├── layout/
│   │   ├── detector.py
│   │   └── label_mapper.py
│   │
│   ├── ocr/
│   │   ├── detector.py
│   │   └── recognizer.py
│   │
│   ├── structure/
│   │   ├── reading_order.py
│   │   ├── title_parser.py
│   │   ├── caption_matcher.py
│   │   └── block_merger.py
│   │
│   ├── assets/
│   │   ├── figure_extractor.py
│   │   └── table_extractor.py
│   │
│   ├── ir/
│   │   └── document.py
│   │
│   └── output/
│       └── markdown_builder.py
│
├── workspace/
│   ├── pages/
│   ├── layout/
│   ├── figures/
│   ├── tables/
│   └── document.json
│
└── output/
    ├── document.md
    └── assets/
```

---

## 19. 推荐 Pipeline

```python
def pdf_to_markdown(pdf_path):

    document = load_pdf(pdf_path)

    pages = render_pages(document)

    all_blocks = []

    for page in pages:

        layout_blocks = layout_model(page.image)

        native_blocks = extract_native_text(page)

        blocks = merge_layout_and_native_text(
            layout_blocks,
            native_blocks
        )

        blocks = run_ocr_if_needed(blocks)

        blocks = remove_headers_footers(blocks)

        blocks = restore_reading_order(blocks)

        blocks = extract_figures(blocks)

        blocks = extract_tables(blocks)

        blocks = associate_captions(blocks)

        all_blocks.extend(blocks)

    document_ir = build_document_structure(all_blocks)

    markdown = render_markdown(document_ir)

    return markdown
```

---

## 20. 模型最终推荐

### MVP

| 模块 | 推荐方案 | 说明 |
|---|---|---|
| PDF Parser | PyMuPDF | 原生文本 + 页面渲染 |
| Layout | DocLayout-YOLO | 轻量、适合本地 |
| OCR | PP-OCRv5 Mobile | 中英文、轻量 |
| Figure | bbox + crop | 第一版足够 |
| Table | bbox + crop | 第一版先保证信息不丢失 |
| Reading Order | Geometry Rules | MVP |
| Formula | 暂缓/保留图片 | 第二阶段 |
| Markdown | Custom Builder | 完全可控 |

推荐核心：

```text
PyMuPDF
+
DocLayout-YOLO
+
PP-OCRv5 Mobile
```

---

## 21. 增强版

如果第一版完成后，需要进一步提升：

```text
复杂双栏
+
标题分类
+
阅读顺序
+
表格
+
公式
```

建议逐步升级：

```text
                    MVP
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
PP-DocLayoutV2   Table Model   Formula Model
       │             │             │
       └─────────────┼─────────────┘
                     ▼
                Better IR
                     │
                     ▼
               Better Markdown
```

不要一开始一次性加入所有模型。

---

## 22. 不建议第一版采用大型 VLM

例如直接采用大型 Vision-Language Model：

```text
PDF Page
↓
VLM
↓
Markdown
```

虽然开发 Demo 很快，但对本项目并不是最佳起点。

原因：

1. 模型体积大；
2. GPU/内存要求更高；
3. 本地 CPU 推理慢；
4. 批量 PDF 成本高；
5. 输出存在不确定性；
6. Bounding Box 可控性较差；
7. Figure/Table 精确裁剪仍需要传统视觉模块；
8. 调试时难以判断错误发生在哪个阶段。

本项目更适合：

```text
模块化
+
轻量模型
+
确定性 Pipeline
+
结构化中间结果
```

---

## 23. 建议开发阶段

### Phase 1：PDF 基础解析

实现：

```text
PDF upload
↓
PyMuPDF
↓
page image
+
native text
```

---

### Phase 2：Layout

加入：

```text
DocLayout-YOLO
```

可视化：

```text
bbox
+
label
+
confidence
```

先确认：

- text
- title
- figure
- table
- caption

检测是否稳定。

---

### Phase 3：Text

实现：

```text
Layout bbox
+
PDF native text bbox
↓
Text Assignment
```

无法匹配：

```text
PP-OCRv5
```

---

### Phase 4：Figure/Table

实现：

```text
bbox
↓
crop
↓
save
```

同时建立 Caption Association。

---

### Phase 5：Reading Order

解决：

```text
single-column
two-column
cross-column figure
cross-column table
```

---

### Phase 6：Document IR

统一：

```text
title
section
paragraph
figure
table
formula
```

---

### Phase 7：Markdown

输出：

```text
document.md
assets/
```

---

### Phase 8：增强

再逐步增加：

```text
Table Structure Recognition
Formula → LaTeX
Reference Parsing
Metadata Extraction
Reading Order Model
LLM Post-processing
```

---

## 24. 最终输出目录

用户输入：

```text
paper.pdf
```

系统输出：

```text
paper/
│
├── paper.md
│
├── document.json
│
└── assets/
    ├── figures/
    │   ├── figure_001.png
    │   ├── figure_002.png
    │   └── ...
    │
    └── tables/
        ├── table_001.png
        ├── table_002.png
        └── ...
```

`document.json` 建议始终保留。

它是整个系统最重要的中间结果之一。

---

## 25. 推荐最终架构

```text
                         PDF
                          │
                          ▼
                      PyMuPDF
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
       Native Text                  Page Image
            │                           │
            │                           ▼
            │                  DocLayout-YOLO
            │                           │
            └─────────────┬─────────────┘
                          ▼
                    Layout Blocks
                          │
                   Native Text Match
                          │
                  ┌───────┴───────┐
                  │               │
               Success           Fail
                  │               │
                  │               ▼
                  │         PP-OCRv5 Mobile
                  │               │
                  └───────┬───────┘
                          ▼
                   Structured Blocks
                          │
             ┌────────────┼────────────┐
             │            │            │
             ▼            ▼            ▼
           Text         Figure        Table
             │            │            │
             │          Crop         Crop
             │            │            │
             └────────────┼────────────┘
                          ▼
                 Caption Association
                          │
                          ▼
                  Reading Order
                          │
                          ▼
                  Title Hierarchy
                          │
                          ▼
                    Document IR
                          │
                          ▼
                  Markdown Builder
                          │
                          ▼
                     paper.md
```

---

## 26. 结论

对于“本地、轻量、可控、可扩展”的 PDF → Markdown Workflow，第一版建议采用：

```text
PyMuPDF
+
DocLayout-YOLO
+
PP-OCRv5 Mobile
+
自定义 Structure Processor
+
自定义 Markdown Builder
```

其中：

- **PyMuPDF**：负责 PDF 原生信息获取；
- **DocLayout-YOLO**：负责页面版面理解；
- **PP-OCRv5 Mobile**：负责扫描件和缺失文本识别；
- **Structure Processor**：负责阅读顺序、标题层级、Caption 关联；
- **Asset Extractor**：负责 Figure/Table 裁剪；
- **Document IR**：作为系统内部统一文档表达；
- **Markdown Builder**：负责最终 `.md` 输出。

第一阶段应优先解决：

> **结构正确、正文不乱、图片不丢、表格不丢、双栏顺序正确。**

而不是一开始追求所有复杂表格和公式都完美转换。

待 MVP 稳定后，再逐步增加：

```text
PP-DocLayoutV2 / 更强阅读顺序模型
+
Table Structure Recognition
+
Formula Recognition
+
Reference Parser
+
LLM-based Structure Correction
```

这种架构既能保持本地模型较小，也便于后续独立替换任何一个模型，而无需重写整个 PDF → Markdown 系统。
