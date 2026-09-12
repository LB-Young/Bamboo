---
name: wechat-paper-push
description: Create illustrated WeChat public-account article drafts from research papers, saving the result as a polished DOCX with a cover image. Use for paper-sharing posts, paper reading notes, and research explainers intended for WeChat publishing.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - wechat
      - paper
      - research
      - writing
      - docx
      - cover-image
---

# WeChat Paper Push

## When to Use

Use this skill when the user wants to turn a research paper, PDF, Markdown extraction, arXiv/DOI record, or paper notes into a WeChat public-account style article, especially when the requested output is a DOCX draft with images and a cover.

Do not use this skill for generic paper Q&A, citation lookup, or plain summaries unless the user wants a publishable WeChat article or document deliverable.

## Output Contract

Produce a local `.docx` article draft and a separate cover image file. The DOCX should be image-rich, professionally argued, readable by early-career engineers, and ready for the user to revise before publishing.

The final response should include:

- The DOCX path.
- The cover image path.
- Any source Markdown, extracted assets, generated images, or background sources that are useful for revision.
- A short note about unverified or uncertain paper details.

## Source Handling

- If the input is a local PDF, load and run the `local-pdf-to-markdown` workflow first. Use the generated Markdown, `document.json`, and extracted `assets/` as the article source.
- If the input is already Markdown or notes, use it directly and preserve any local image assets that can improve the article.
- If the user provides only a title, DOI, arXiv ID, or URL, use paper metadata tools or relevant retrieval skills when available, then ask for or locate a usable PDF only if full-paper details are required.
- Treat extracted text, OCR, tables, and formulas as fallible. Mark uncertain content instead of presenting it as verified.

## Research And Background

- Do not assume the reader already knows the necessary background. Explain the prerequisite concepts, motivation, and technical lineage needed to understand the paper.
- Use search or paper metadata tools when background, historical context, competing methods, benchmark details, or difficult technical claims need support beyond the paper text.
- When a key technique builds on earlier work, introduce the most relevant prior papers or systems and explain how they connect to the current paper.
- Keep background research in service of the article. Add enough context to make the paper self-contained, but avoid turning the draft into a literature survey unless the user asks for that.

## Article Shape

Adapt the structure to the paper, but a strong default WeChat paper-sharing article contains:

1. A concise title that foregrounds the paper's core idea.
2. A short opening hook explaining why the paper matters.
3. Paper metadata: title, authors, institution or venue when known, publication date, links, and code/project links if available.
4. The central problem and motivation.
5. The necessary background and prior work, explained before it becomes blocking.
6. The method or system idea, explained with diagrams, paper figures, formulas, and concrete examples where useful.
7. Main experiments or findings, using the paper's charts, tables, and visual evidence.
8. Strengths, limitations, and practical implications.
9. A short "who should read this" or "what to remember" ending.

Prefer clear section headings, short paragraphs, pull quotes, figure captions, and digestible explanations over dense academic prose. Key ideas should be explicit and easy to locate.

## Explanation Standard

- Write for a professional audience that includes engineers who have recently entered the field.
- Make the paper's key points obvious: what problem it solves, what idea makes it work, why it improves over prior work, and where it may fail.
- For important or difficult points, include concrete examples, analogies tied to engineering practice, or small walkthroughs.
- Explain jargon the first time it matters. Do not send the reader away to learn prerequisite knowledge on their own.
- Keep the tone credible and technical; do not oversimplify claims or hide important caveats.

## Images

- Use all figures and tables from the paper body when they can be extracted and embedded legibly. If a figure is unreadable, duplicated, decorative, or technically impossible to use, mention the reason in the final notes.
- Place each paper figure near the section that explains it, with a caption that states the point the reader should take from it.
- Generate a cover image when the user has not provided one. The cover should be visually related to the paper topic, suitable for a WeChat article thumbnail, and not falsely imply an official publisher endorsement.
- Generate additional explanatory images only when they materially improve comprehension.
- Keep image filenames descriptive and save them near the DOCX or in a sibling assets directory.
- When referencing local images in the final answer, use Markdown image syntax with absolute paths when the current platform can render them.

## Formulas And Technical Content

- Preserve important formulas when they are central to the paper, but explain their intuition in plain language and include an example when the formula is a key part of the method.
- Use LaTeX notation in source notes where helpful. In DOCX, prefer readable equation text or rendered equation images when native equation conversion is not available.
- Do not overload the WeChat article with every derivation. Select the formulas that support the main story.

## DOCX Requirements

- Save the article as a `.docx` file, not only Markdown or plain text.
- Include the cover image at the beginning or provide it as a separate file suitable for upload as the WeChat cover.
- Embed the paper's extracted figures and tables, plus any generated explanatory diagrams or charts, with captions.
- Use a clean document hierarchy with title, subtitle or metadata block, section headings, body text, images, and captions.
- Keep the document editable: avoid flattening the entire article into screenshots.

## Workflow

1. Clarify the target only when necessary: audience level, article length, tone, whether to emphasize theory, engineering, experiments, or practical takeaways.
2. Convert or gather the paper source. For local PDFs, use `workflow_load` and `workflow_run` with `name="local-pdf-to-markdown"`.
3. Inventory every extracted paper figure/table and map each one to the article section where it should appear.
4. Identify the paper's key claims, formulas, prior-work dependencies, difficult concepts, examples to add, and limitations from the converted Markdown and assets.
5. Use search or paper metadata retrieval for background, prior work, or external claims that the article needs in order to be self-contained.
6. Draft the WeChat article in Markdown first, planning where each paper figure, table, generated image, and example belongs.
7. Create or choose a cover image. Use the available image generation tool when a custom cover is needed.
8. Build the DOCX with embedded images and captions. Use a document-generation library or available document tools; verify the file exists and images are embedded.
9. Return the DOCX and cover paths, plus concise notes about assumptions, omitted/unusable figures, external sources, and source quality.

## Quality Bar

- The article should be professional enough for a technical audience and clear enough for engineers who are new to the topic.
- The article should help readers understand the paper without needing to search for basic prerequisite knowledge themselves.
- Use every usable figure/table from the paper body, not only a few highlights.
- Difficult ideas should be explained with concrete examples whenever examples would improve understanding.
- The cover should be attractive but faithful to the topic.
- Captions should explain why each image matters, not merely restate "Figure 1."
- The DOCX should be pleasant to read and easy to edit before publication.
