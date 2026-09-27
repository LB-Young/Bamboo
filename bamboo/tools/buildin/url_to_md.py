"""Download a web page and save readable Markdown locally."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx

from bamboo.security.url_safety import is_url_allowed
from bamboo.tools.buildin.base import Tool, ToolResult

DEFAULT_TIMEOUT = 20.0
DEFAULT_MAX_BYTES = 5_000_000
MIN_CONTENT_CHARS = 240
MIN_CONTENT_WORDS = 25
BLOCKED_CONTENT_PATTERNS = (
    "access denied",
    "are you a robot",
    "attention required",
    "captcha",
    "checking your browser",
    "cloudflare",
    "enable javascript",
    "forbidden",
    "just a moment",
    "please verify",
    "request blocked",
    "service unavailable",
    "too many requests",
    "无法访问",
    "访问被拒绝",
    "请开启 javascript",
    "验证码",
)


class UrlToMarkdownTool(Tool):
    """Fetch a public URL, convert the page to Markdown, and save it to disk."""

    name = "url_to_md"
    description = (
        "Download a public HTTP(S) blog/article page, convert it to Markdown, and save it locally. "
        "Use output_path for an exact file or output_dir for automatic naming. "
        "Falls back to Jina Reader when direct extraction fails; set JINA_API_KEY for authenticated Jina requests."
    )
    risk_level = "network"
    tags = ("web", "network", "markdown", "write")

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.transport = transport
        self.timeout = timeout

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Public HTTP(S) article or blog URL."},
                "output_path": {"type": "string", "description": "Optional exact Markdown output path."},
                "output_dir": {"type": "string", "description": "Directory for auto-named Markdown output."},
                "filename": {"type": "string", "description": "Optional filename when using output_dir."},
                "overwrite": {"type": "boolean", "description": "Overwrite an existing Markdown file."},
                "include_frontmatter": {"type": "boolean", "description": "Include source metadata at the top."},
                "use_jina_fallback": {"type": "boolean", "description": "Use Jina Reader fallback when local extraction fails."},
                "max_bytes": {"type": "integer", "description": "Maximum response bytes to accept."},
            },
            "required": ["url"],
        }

    async def execute(
        self,
        url: str,
        output_path: str = "",
        output_dir: str = "",
        filename: str = "",
        overwrite: bool = False,
        include_frontmatter: bool = True,
        use_jina_fallback: bool = True,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> ToolResult:
        allowed, reason = is_url_allowed(url)
        if not allowed:
            return ToolResult(content=f"URL blocked: {reason}", success=False, error="url_blocked")

        if output_path.strip() and not overwrite:
            destination = Path(output_path).expanduser()
            destination = destination if destination.suffix else destination.with_suffix(".md")
            if destination.exists():
                return ToolResult(
                    content=f"Output already exists: {destination}",
                    success=False,
                    error="output_exists",
                    metadata={"path": str(destination), "url": url},
                )

        limit = max(1, min(max_bytes or DEFAULT_MAX_BYTES, DEFAULT_MAX_BYTES))
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                return ToolResult(content=f"Fetch failed: {exc}", success=False, error="fetch_failed")

            raw = response.content
            if len(raw) > limit:
                return ToolResult(
                    content=f"Response too large: {len(raw)} bytes exceeds limit {limit}",
                    success=False,
                    error="response_too_large",
                    metadata={"url": str(response.url), "bytes": len(raw), "max_bytes": limit},
                )
            text = response.text
            content_type = response.headers.get("content-type", "")
            final_url = str(response.url)
            if "html" in content_type.lower() or "<html" in text[:1000].lower():
                title = extract_title(text) or title_from_url(final_url)
                markdown = html_to_markdown(text, base_url=final_url).strip()
            else:
                title = title_from_url(final_url)
                markdown = text.strip()
            extracted = {
                "url": final_url,
                "title": title,
                "markdown": markdown,
                "bytes": len(raw),
                "content_type": content_type,
            }
            extraction_source = "direct"
            validation = validate_markdown_content(extracted["markdown"])
            if not validation[0] and use_jina_fallback:
                try:
                    api_key = os.environ.get("JINA_API_KEY", "").strip()
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    jina_response = await client.get(f"https://r.jina.ai/{url}", headers=headers)
                    jina_response.raise_for_status()
                except httpx.HTTPError as exc:
                    return ToolResult(
                        content="无法提取网页正文内容。",
                        success=False,
                        error="extraction_failed",
                        metadata={"url": url, "direct_reason": validation[1], "jina_error": str(exc)},
                    )
                jina_raw = jina_response.content
                if len(jina_raw) > limit:
                    return ToolResult(
                        content="无法提取网页正文内容。",
                        success=False,
                        error="extraction_failed",
                        metadata={
                            "url": url,
                            "direct_reason": validation[1],
                            "jina_error": f"Response too large: {len(jina_raw)} bytes exceeds limit {limit}",
                            "jina_bytes": len(jina_raw),
                            "max_bytes": limit,
                        },
                    )
                jina_markdown = jina_response.text.strip()
                jina_title = title_from_url(url)
                for line in jina_markdown.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        jina_title = stripped.lstrip("#").strip()
                        break
                    if stripped.lower().startswith("title:"):
                        jina_title = stripped.split(":", 1)[1].strip()
                        break
                extracted = {
                    "url": url,
                    "title": jina_title,
                    "markdown": jina_markdown,
                    "bytes": len(jina_raw),
                    "content_type": jina_response.headers.get("content-type", ""),
                }
                extraction_source = "jina"
                validation = validate_markdown_content(extracted["markdown"])

        if not validation[0]:
            return ToolResult(
                content="无法提取网页正文内容。",
                success=False,
                error="extraction_failed",
                metadata={"url": url, "reason": validation[1], "source": extraction_source},
            )

        final_url = extracted["url"]
        title = extracted["title"]
        markdown = extracted["markdown"]

        if include_frontmatter:
            timestamp = datetime.now(UTC).isoformat()
            markdown = "\n".join(
                [
                    "---",
                    f"title: {json.dumps(title, ensure_ascii=False)}",
                    f"source_url: {json.dumps(final_url, ensure_ascii=False)}",
                    f"saved_at: {json.dumps(timestamp, ensure_ascii=False)}",
                    "---",
                    "",
                    markdown,
                ]
            ).strip() + "\n"
        else:
            markdown += "\n"

        destination = resolve_output_path(final_url, title, output_path=output_path, output_dir=output_dir, filename=filename)
        if destination.exists() and not overwrite:
            return ToolResult(
                content=f"Output already exists: {destination}",
                success=False,
                error="output_exists",
                metadata={"path": str(destination), "url": final_url},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(markdown, encoding="utf-8")
        return ToolResult(
            content=f"Saved Markdown to {destination}",
            metadata={
                "path": str(destination),
                "url": final_url,
                "title": title,
                "bytes": extracted["bytes"],
                "content_type": extracted["content_type"],
                "extraction_source": extraction_source,
            },
        )


def validate_markdown_content(markdown: str) -> tuple[bool, str]:
    text = markdown.strip()
    if len(text) < MIN_CONTENT_CHARS:
        return False, "content_too_short"
    lowered = text.lower()
    if any(pattern in lowered for pattern in BLOCKED_CONTENT_PATTERNS):
        return False, "blocked_or_error_page"
    plain = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", text)
    plain = re.sub(r"\[[^\]]+]\([^)]*\)", " ", plain)
    words = re.findall(r"[\w\u4e00-\u9fff]+", plain, flags=re.UNICODE)
    if len(words) < MIN_CONTENT_WORDS:
        return False, "not_enough_text"
    structure_score = 0
    structure_score += 1 if re.search(r"(?m)^#{1,6}\s+\S", text) else 0
    structure_score += 1 if len(re.findall(r"\n\s*\n", text)) >= 2 else 0
    structure_score += 1 if len(re.findall(r"[。.!?]\s", plain)) >= 3 else 0
    if structure_score == 0:
        return False, "missing_article_structure"
    return True, "ok"


class _TitleExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.parts.append(data)


class _MarkdownExtractor(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.parts: list[str] = []
        self.skip_depth = 0
        self.in_pre = False
        self.inline_code_depth = 0
        self.href_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = dict(attrs)
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {"article", "main", "section", "div", "p"}:
            self.parts.append("\n\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            self.parts.append("\n\n" + ("#" * level) + " ")
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "blockquote":
            self.parts.append("\n\n> ")
        elif tag == "pre":
            self.in_pre = True
            self.parts.append("\n\n```\n")
        elif tag == "code" and not self.in_pre:
            self.inline_code_depth += 1
            self.parts.append("`")
        elif tag == "a":
            href = attributes.get("href") or ""
            self.href_stack.append(urllib.parse.urljoin(self.base_url, href) if href else "")
        elif tag == "img":
            src = attributes.get("src") or ""
            if src:
                alt = clean_inline(attributes.get("alt") or "image")
                self.parts.append(f"![{alt}]({urllib.parse.urljoin(self.base_url, src)}) ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"article", "main", "section", "div", "p", "blockquote"}:
            self.parts.append("\n\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6", "li"}:
            self.parts.append("\n")
        elif tag == "pre":
            self.in_pre = False
            self.parts.append("\n```\n\n")
        elif tag == "code" and self.inline_code_depth and not self.in_pre:
            self.inline_code_depth -= 1
            self.parts.append("`")
        elif tag == "a" and self.href_stack:
            self.href_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.in_pre:
            self.parts.append(data)
            return
        text = clean_inline(data)
        if not text:
            return
        if self.href_stack and self.href_stack[-1]:
            self.parts.append(f"[{text}]({self.href_stack[-1]}) ")
        else:
            self.parts.append(text + " ")


def extract_title(html: str) -> str:
    parser = _TitleExtractor()
    parser.feed(html)
    return clean_inline(" ".join(parser.parts))


def html_to_markdown(html: str, *, base_url: str) -> str:
    parser = _MarkdownExtractor(base_url=base_url)
    parser.feed(html)
    return normalize_markdown("".join(parser.parts))


def clean_inline(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def normalize_markdown(markdown: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in markdown.splitlines()]
    collapsed = "\n".join(lines)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    collapsed = re.sub(r"(?m)^# +$", "", collapsed)
    return collapsed.strip()


def resolve_output_path(
    url: str,
    title: str,
    *,
    output_path: str = "",
    output_dir: str = "",
    filename: str = "",
) -> Path:
    if output_path.strip():
        path = Path(output_path).expanduser()
        return path if path.suffix else path.with_suffix(".md")
    directory = Path(output_dir).expanduser() if output_dir.strip() else Path.cwd() / "url-to-md"
    name = filename.strip() or f"{slugify(title or title_from_url(url)) or 'page'}.md"
    if not name.lower().endswith(".md"):
        name += ".md"
    return directory / safe_filename(name)


def title_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path_name = Path(parsed.path).name
    return urllib.parse.unquote(path_name or parsed.netloc or "page").strip()


def slugify(value: str) -> str:
    value = urllib.parse.unquote(value).strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    return value.strip("-_")[:120]


def safe_filename(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", value).strip() or "page.md"
