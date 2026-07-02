"""LSP tool tests."""

from __future__ import annotations

import pytest

from bamboo.tools.buildin.lsp import LSPTool


@pytest.mark.asyncio
async def test_lsp_tool_returns_not_configured_for_supported_operation(tmp_path) -> None:
    path = tmp_path / "demo.py"
    path.write_text("x = 1\n", encoding="utf-8")

    result = await LSPTool().execute("hover", str(path), line=0, character=1)

    assert result.success is False
    assert result.error == "lsp_not_configured"
    assert result.metadata["operation"] == "hover"


@pytest.mark.asyncio
async def test_lsp_tool_rejects_unknown_operation(tmp_path) -> None:
    path = tmp_path / "demo.py"
    path.write_text("x = 1\n", encoding="utf-8")

    result = await LSPTool().execute("rename", str(path))

    assert result.success is False
    assert result.error == "unsupported_operation"
