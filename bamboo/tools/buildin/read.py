"""内置文件读取工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.buildin.file_filter import should_skip_for_read


class ReadTool(Tool):
    """读取 UTF-8 文本文件，并支持按行截取。"""

    name = "read"
    description = "Read the content of a text file with optional line offset and limit."

    def input_schema(self) -> dict[str, Any]:
        """返回读取文件的参数 schema。"""
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to read."},
                "offset": {"type": "integer", "description": "Zero-based start line."},
                "limit": {"type": "integer", "description": "Maximum number of lines to read."},
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str, offset: int = 0, limit: int | None = None) -> ToolResult:
        """读取文本文件并返回指定行范围。"""
        path = Path(file_path).expanduser()
        if not path.exists():
            return ToolResult(content=f"File not found: {path}", success=False, error="file_not_found")
        if not path.is_file():
            return ToolResult(content=f"Not a file: {path}", success=False, error="not_a_file")

        skip, reason = should_skip_for_read(path)
        if skip:
            return ToolResult(content=reason, success=False, error="unsupported_file")

        # errors="replace" 可以避免少量非法字符导致整个读取失败。
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(offset, 0)
        end = start + limit if limit is not None else len(lines)
        selected = lines[start:end]
        return ToolResult(content=f"[lines {start}:{start + len(selected)}]\n" + "\n".join(selected))
