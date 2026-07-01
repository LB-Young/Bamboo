"""内置精确字符串编辑工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult


class EditTool(Tool):
    """在 UTF-8 文本文件中替换一次精确匹配的字符串。"""

    name = "edit"
    description = "Replace one exact string in an existing UTF-8 text file."
    risk_level = "write"
    tags = ("filesystem", "write")

    def input_schema(self) -> dict[str, Any]:
        """返回精确编辑的参数 schema。"""
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to edit."},
                "old_string": {"type": "string", "description": "Exact string to replace."},
                "new_string": {"type": "string", "description": "Replacement string."},
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    async def execute(self, file_path: str, old_string: str, new_string: str) -> ToolResult:
        """把 old_string 的第一次精确出现替换为 new_string。"""
        path = Path(file_path).expanduser()
        if not path.exists():
            return ToolResult(content=f"File not found: {path}", success=False, error="file_not_found")
        if not path.is_file():
            return ToolResult(content=f"Not a file: {path}", success=False, error="not_a_file")
        if old_string == "":
            return ToolResult(content="old_string must not be empty", success=False, error="empty_old_string")

        # 使用精确字符串匹配，避免正则替换造成意外范围扩大。
        original = path.read_text(encoding="utf-8")
        if old_string not in original:
            return ToolResult(content=f"old_string not found in {path}", success=False, error="old_string_not_found")

        path.write_text(original.replace(old_string, new_string, 1), encoding="utf-8")
        return ToolResult(content=f"Edited {path}")
