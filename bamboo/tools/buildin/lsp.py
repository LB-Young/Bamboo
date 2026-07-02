"""Read-only LSP-style code intelligence tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult


SUPPORTED_OPERATIONS = {"go_to_definition", "find_references", "hover", "document_symbols"}


class LSPTool(Tool):
    """Stable interface for future language-server backed code intelligence."""

    name = "lsp"
    description = "Read-only semantic code query interface for definitions, references, hover, and symbols."
    risk_level = "read"
    tags = ("code", "lsp", "read")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "One of go_to_definition, find_references, hover, document_symbols.",
                },
                "file_path": {"type": "string", "description": "Source file path."},
                "line": {"type": "integer", "description": "Zero-based line number."},
                "character": {"type": "integer", "description": "Zero-based character offset."},
            },
            "required": ["operation", "file_path"],
        }

    async def execute(
        self,
        operation: str,
        file_path: str,
        line: int = 0,
        character: int = 0,
    ) -> ToolResult:
        if operation not in SUPPORTED_OPERATIONS:
            return ToolResult(
                content=f"Unsupported LSP operation: {operation}",
                success=False,
                error="unsupported_operation",
            )
        path = Path(file_path).expanduser()
        if not path.is_file():
            return ToolResult(content=f"File not found: {path}", success=False, error="file_not_found")
        return ToolResult(
            content=(
                "No LSP server is configured yet. "
                f"Received {operation} request for {path}:{max(line, 0)}:{max(character, 0)}."
            ),
            success=False,
            error="lsp_not_configured",
            metadata={
                "operation": operation,
                "file_path": str(path),
                "line": max(line, 0),
                "character": max(character, 0),
            },
        )
