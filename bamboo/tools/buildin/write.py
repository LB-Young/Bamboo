"""内置文件写入工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult


class WriteTool(Tool):
    """创建或覆盖 UTF-8 文本文件。"""

    name = "write"
    description = "Write UTF-8 text content to a file, creating parent directories if needed."

    def input_schema(self) -> dict[str, Any]:
        """返回写入文件的参数 schema。"""
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to write."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, file_path: str, content: str) -> ToolResult:
        """写入文件内容，并返回简短摘要。"""
        path = Path(file_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(content=f"Wrote {len(content.encode('utf-8'))} bytes to {path}")
