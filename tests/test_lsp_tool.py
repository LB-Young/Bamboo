"""LSP tool tests."""

from __future__ import annotations

import pytest

from bamboo.tools.buildin.lsp import LSPTool


@pytest.mark.asyncio
async def test_lsp_tool_returns_document_symbols_for_python_file(tmp_path) -> None:
    path = tmp_path / "demo.py"
    path.write_text(
        "\n".join(
            [
                "class Service:",
                "    def handle(self, value):",
                "        return helper(value)",
                "",
                "def helper(value):",
                "    return value + 1",
            ]
        ),
        encoding="utf-8",
    )

    result = await LSPTool().execute("document_symbols", str(path))

    assert result.success is True
    assert result.metadata["count"] == 3
    assert [item["qualified_name"] for item in result.metadata["symbols"]] == [
        "Service",
        "Service.handle",
        "helper",
    ]


@pytest.mark.asyncio
async def test_lsp_tool_finds_definition_and_references(tmp_path) -> None:
    path = tmp_path / "demo.py"
    path.write_text(
        "\n".join(
            [
                "def helper(value):",
                "    return value + 1",
                "",
                "def caller():",
                "    return helper(41)",
            ]
        ),
        encoding="utf-8",
    )

    definition = await LSPTool().execute("go_to_definition", str(path), line=4, character=13)
    references = await LSPTool().execute("find_references", str(path), symbol_name="helper")

    assert definition.success is True
    assert definition.metadata["definitions"][0]["name"] == "helper"
    assert definition.metadata["definitions"][0]["line"] == 0
    assert references.success is True
    assert references.metadata["count"] == 2


@pytest.mark.asyncio
async def test_lsp_tool_hover_returns_signature_and_docstring(tmp_path) -> None:
    path = tmp_path / "demo.py"
    path.write_text(
        '\n'.join(
            [
                "def helper(value: int) -> int:",
                '    """Increment a value."""',
                "    return value + 1",
                "",
                "result = helper(1)",
            ]
        ),
        encoding="utf-8",
    )

    result = await LSPTool().execute("hover", str(path), line=4, character=10)

    assert result.success is True
    assert "signature: def helper(value: int) -> int" in result.content
    assert "Increment a value." in result.content


@pytest.mark.asyncio
async def test_lsp_tool_reports_python_syntax_error(tmp_path) -> None:
    path = tmp_path / "broken.py"
    path.write_text("def broken(:\n", encoding="utf-8")

    result = await LSPTool().execute("diagnostics", str(path))

    assert result.success is False
    assert result.error == "syntax_error"
    assert result.metadata["diagnostics"][0]["severity"] == "error"


@pytest.mark.asyncio
async def test_lsp_tool_rejects_unknown_operation(tmp_path) -> None:
    path = tmp_path / "demo.py"
    path.write_text("x = 1\n", encoding="utf-8")

    result = await LSPTool().execute("rename", str(path))

    assert result.success is False
    assert result.error == "unsupported_operation"
