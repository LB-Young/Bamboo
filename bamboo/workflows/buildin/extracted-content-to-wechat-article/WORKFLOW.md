---
name: extracted-content-to-wechat-article
description: Build a WeChat public-account article package from an extracted content directory and an article Markdown draft.
usage: |
  1. Extract source material first. The extractor can be a workflow, skill, or tool for PDFs, web pages, videos, social posts, or WeChat articles.
  2. Put the extracted Markdown and local assets under one content directory, then draft the WeChat article as Markdown.
  3. Use LaTeX for formulas (`$...$` or `$$...$$`) and Markdown image links for selected local images/tables.
  4. Call `workflow_load` with `name="extracted-content-to-wechat-article"`.
  5. Generate or choose a local cover image before building the package.
  6. Call `workflow_run` with arguments:
     `"<content-dir> <article-draft.md> <output-dir> [--title TITLE] --cover <cover.png> [--verify-links]"`
     Use `--no-cover` only when the user explicitly says no cover is needed.
  7. The workflow returns paths for the DOCX, normalized Markdown, asset manifest, link report, and quality report.
dependencies:
- python-docx
- Pillow
- matplotlib (optional, for rendering block LaTeX formulas as DOCX images)
---

# Extracted Content To WeChat Article Workflow

## 功能

基于任意上游内容提取结果和一份公众号文章 Markdown 草稿，构建一套可发布前审阅的文章包。

这个 workflow 不负责“下载/抓取/转写/凭空写文章”。上游可以是论文 PDF、网页、B 站/抖音视频、知乎内容、其他公众号文章或后续新增的数据源；你应先用合适的 tool、skill 或 workflow 把源材料提取成 Markdown、本地图片、本地表格等文件，再把这些提取结果交给本 workflow。

写作仍由 Agent 根据提取后的 Markdown、资产和用户要求完成。本 workflow 负责把容易出错、需要一致执行的工程环节标准化：

- 统一生成 `.docx`。
- 保留一份规范化 Markdown，供支持 LaTeX 的公众号 Markdown 编辑器使用。
- 识别 Markdown 中使用的图片/表格，并和内容目录中的本地资产交验。
- 对未使用的重要图表给出报告，要求 Agent 在最终回复里说明保留或舍弃原因。
- 将 block LaTeX 公式渲染为 DOCX 中可读图片；Markdown 中保留 LaTeX 源码。
- 校验文章中的网络链接是否可访问，并输出状态报告。
- 输出质量报告，包括段落数、图片数、公式数、链接数、未使用重要资产等。

## 输入约定

```text
<content-dir> <article-draft.md> <output-dir> [--title TITLE] --cover <cover.png> [--verify-links]
```

- `<content-dir>`：上游提取结果目录。推荐包含一个或多个 Markdown 文件，以及 `assets/` 下的图片、表格截图、视频关键帧、网页截图等。
- `<article-draft.md>`：Agent 写好的公众号文章 Markdown。
- `<output-dir>`：文章包输出目录。
- `--title`：可选，覆盖 DOCX 标题；默认取 Markdown 第一个一级标题。
- `--cover`：封面图路径。默认必须提供，因为公众号推送通常需要封面图。封面图可以由图片生成工具生成、从源材料中选择，或由用户提供。
- `--no-cover`：显式允许不带封面构建。只有用户明确说不需要封面时才使用。
- `--verify-links`：可选，联网校验 Markdown 中的 `http(s)` 链接。

> 由于 Bamboo 当前 `workflow_run` 将参数作为一个字符串传给脚本，路径包含空格时请使用 shell 风格引号。

## Markdown 写作约定

- 公式：
  - 行内公式：`$S_t = ...$`
  - 块公式：

    ```markdown
    $$
    S_t = (D_t - a_t b_t^\top) S_{t-1} + k_t v_t^\top
    $$
    ```

- 图片和表格：
  - 使用 Markdown 图片语法：`![图注](assets/images/demo.png)`、`![表 1：对比结果](assets/tables/table_001.png)`。
  - 路径可以相对文章 Markdown、相对内容目录，或使用绝对路径。
  - 重要图表应该入文；不入文时在最终说明里解释“重复/太细/附录/不可读/与主线无关”。

- 链接：
  - 使用普通 Markdown 链接：`[MoonshotAI/Kimi-Linear](https://github.com/MoonshotAI/Kimi-Linear)`。
  - 开启 `--verify-links` 后，workflow 会输出 `link_report.md`。

## 输出约定

运行成功后，stdout 包含：

```text
DOCX: /absolute/path/article.docx
Markdown: /absolute/path/article.normalized.md
AssetManifest: /absolute/path/asset_manifest.md
LinkReport: /absolute/path/link_report.md
QualityReport: /absolute/path/quality_report.md
FormulaAssets: /absolute/path/formulas
```

## 推荐执行顺序

1. 针对源材料运行合适的提取流程，例如：
   - 论文：下载/定位 PDF 后运行 `local-pdf-to-markdown`。
   - 网页/知乎/公众号：用网页提取工具生成 Markdown 和本地图片。
   - 视频：用视频/字幕提取工具生成摘要 Markdown、字幕、关键帧和表格截图。
2. Agent 阅读提取后的 Markdown 和本地资产，写 `article-draft.md`。
3. 做一次“外部补充信息审查”：检查草稿中是否出现需要核验或补充的内容，例如论文元数据、项目/代码仓库链接、发布时间、作者机构、背景脉络、竞品/前作、数据口径、网络热度、引用来源等。需要时先调用合适的 search、metadata、reach skill 或其他检索 workflow 补齐，再修改草稿。
4. 在草稿中用 LaTeX 写公式，用 Markdown 图片语法引用选中的图片、表格或关键帧。
5. 生成或选择封面图：默认应产出一张本地封面图，即使用户后续可以不用。封面图应贴合主题，不冒充官方发布，不使用不可确认版权的远程素材；可以用图片生成工具、源材料中的核心图、视频关键帧或用户提供素材。
6. 做一次“去 AI 味编辑审查”：加载 `humanize-writing` skill，检查标题、开头、段落节奏、图注、结尾和列表是否有明显 AI 写作痕迹；如果有，先改稿。
7. 做一次“内容质量审查”：加载 `article-quality-review` skill，检查文章主线、信息密度、证据支撑、图表解释、废话比例、结论质量和读者收益。发现废话、弱论证或未解释图表时，必须先改稿；不要把低质量草稿直接打包。
8. 运行本 workflow 构建文章包，默认传入 `--cover <cover.png>`；只有用户明确表示不需要封面时才传 `--no-cover`。
9. 检查 `asset_manifest.md`、`quality_report.md`、`link_report.md`。
10. 如果存在“重要但未使用”的图表、失败链接、未渲染公式、缺失图片或明显发布兼容风险，Agent 必须修订草稿或在最终说明中解释。

## 公众号发布兼容性说明

本 workflow 的目标不是只生成一个文件，而是生成一套“导入公众号后台前可检查、可修订”的文章包。公众号后台、第三方 Markdown-to-WeChat 编辑器、DOCX 导入链路可能会对公式、图片、表格、链接、样式和排版产生不同程度的兼容问题；发现新问题后，应把它沉淀为本节的一条发布注意事项，并尽量在脚本中加入对应的检查或转换。

当前已知规则：

- 公式：微信公众号后台直接导入 DOCX 时通常不会把普通字符串自动渲染成数学公式。本 workflow 采用双轨输出：Markdown 中保留 LaTeX 源码，适合进入支持 LaTeX 的 Markdown-to-WeChat 编辑器；DOCX 中把 block LaTeX 公式渲染为图片，保证视觉可读。若渲染失败，会保留 LaTeX 源码并在 `quality_report.md` 中记录。
- 图片和表格：文章中引用的本地图片会复制到输出包，并嵌入 DOCX；未引用但看起来重要的本地图片/表格会出现在 `asset_manifest.md` 和 `quality_report.md` 中，供发布前决定是否补入正文或说明舍弃原因。
- 链接：开启 `--verify-links` 后，网络链接会写入 `link_report.md`；失败链接必须修正或在最终说明中标记为未核验。
- 后续新增问题：如果实际公众号导入中发现新的兼容问题，例如图片尺寸、表格清晰度、样式丢失、链接跳转、特殊字符、代码块、脚注或视频卡片等，应在这里增加规则，并让 workflow 输出明确的报告项。
