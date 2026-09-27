from __future__ import annotations

import httpx
import pytest

import bamboo.tools.buildin.url_to_md as url_to_md_module
from bamboo.tools.buildin.url_to_md import UrlToMarkdownTool
from bamboo.tools.registry import create_tool_registry


@pytest.mark.asyncio
async def test_url_to_md_saves_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(url_to_md_module, "is_url_allowed", lambda url: (True, "allowed"))

    html = """
    <html>
      <head><title>Example Blog</title><style>.x{}</style></head>
      <body>
        <article>
          <h1>Hello Blog</h1>
          <p>Read <a href="/more">more</a> now. This article has enough real content to pass extraction validation. It describes a research blog post, explains why the idea matters, and gives readers useful context before saving it locally.</p>
          <p>The second paragraph adds details, examples, and conclusions. It is normal article prose rather than a login screen, anti-bot challenge, or placeholder page. The Markdown converter should keep links, lists, code, and images.</p>
          <ul><li>First</li><li>Second</li></ul>
          <pre><code>print("hi")</code></pre>
          <img src="/image.png" alt="diagram">
        </article>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=html)

    tool = UrlToMarkdownTool(transport=httpx.MockTransport(handler))
    result = await tool.execute("https://example.com/blog/post", output_dir=str(tmp_path))

    assert result.success
    path = tmp_path / "example-blog.md"
    content = path.read_text(encoding="utf-8")
    assert 'title: "Example Blog"' in content
    assert "source_url:" in content
    assert "# Hello Blog" in content
    assert "Read [more](https://example.com/more) now." in content
    assert "[more](https://example.com/more)" in content
    assert "- First" in content
    assert 'print("hi")' in content
    assert "![diagram](https://example.com/image.png)" in content


@pytest.mark.asyncio
async def test_url_to_md_refuses_existing_output(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(url_to_md_module, "is_url_allowed", lambda url: (True, "allowed"))
    output = tmp_path / "page.md"
    output.write_text("existing", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<title>New</title><p>Body</p>")

    tool = UrlToMarkdownTool(transport=httpx.MockTransport(handler))
    result = await tool.execute("https://example.com/page", output_path=str(output))

    assert not result.success
    assert result.error == "output_exists"
    assert output.read_text(encoding="utf-8") == "existing"


def test_url_to_md_is_registered() -> None:
    registry = create_tool_registry()
    assert registry.get("url_to_md") is not None


@pytest.mark.asyncio
async def test_url_to_md_uses_jina_fallback_when_direct_content_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(url_to_md_module, "is_url_allowed", lambda url: (True, "allowed"))
    monkeypatch.setenv("JINA_API_KEY", "test-jina-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith("https://r.jina.ai/"):
            assert request.headers["Authorization"] == "Bearer test-jina-key"
            return httpx.Response(
                200,
                headers={"content-type": "text/plain; charset=utf-8"},
                text=(
                    "# Good Blog\n\n"
                    "This is a normal article with enough useful content. "
                    "It explains the background, gives details, and includes conclusions. "
                    "Readers can save this markdown locally for later research.\n\n"
                    "The second paragraph adds more context, evidence, and practical notes. "
                    "It is clearly not an error page or an anti-bot challenge."
                ),
            )
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<title>Blocked</title>Access denied")

    tool = UrlToMarkdownTool(transport=httpx.MockTransport(handler))
    result = await tool.execute("https://example.com/blocked", output_dir=str(tmp_path))

    assert result.success
    assert result.metadata is not None
    assert result.metadata["extraction_source"] == "jina"
    content = (tmp_path / "good-blog.md").read_text(encoding="utf-8")
    assert "# Good Blog" in content


@pytest.mark.asyncio
async def test_url_to_md_returns_extraction_failed_without_writing_bad_content(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(url_to_md_module, "is_url_allowed", lambda url: (True, "allowed"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<title>Nope</title>captcha")

    output = tmp_path / "bad.md"
    tool = UrlToMarkdownTool(transport=httpx.MockTransport(handler))
    result = await tool.execute("https://example.com/bad", output_path=str(output))

    assert not result.success
    assert result.error == "extraction_failed"
    assert result.content == "无法提取网页正文内容。"
    assert not output.exists()
