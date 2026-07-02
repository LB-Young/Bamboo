"""内置精确字符串编辑工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult


class EditTool(Tool):
    """在 UTF-8 文本文件中执行精确字符串编辑。"""

    name = "edit"
    description = "Replace exact strings in an existing UTF-8 text file, including all-or-nothing multi_replace."
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
                "mode": {
                    "type": "string",
                    "description": "Edit mode: replace or multi_replace.",
                },
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        },
                        "required": ["old", "new"],
                    },
                    "description": "All-or-nothing replacement list for mode=multi_replace.",
                },
            },
            "required": ["file_path"],
        }

    async def execute(
        self,
        file_path: str,
        old_string: str = "",
        new_string: str = "",
        mode: str = "replace",
        edits: list[dict[str, str]] | None = None,
    ) -> ToolResult:
        """执行单次替换或多处全量匹配替换。"""
        path = Path(file_path).expanduser()
        if not path.exists():
            return ToolResult(content=f"File not found: {path}", success=False, error="file_not_found")
        if not path.is_file():
            return ToolResult(content=f"Not a file: {path}", success=False, error="not_a_file")
        if mode not in {"replace", "multi_replace"}:
            return ToolResult(content=f"Unsupported edit mode: {mode}", success=False, error="unsupported_mode")

        original = path.read_text(encoding="utf-8")
        if mode == "multi_replace":
            return self._multi_replace(path, original, edits or [])

        if old_string == "":
            return ToolResult(content="old_string must not be empty", success=False, error="empty_old_string")

        # 使用精确字符串匹配，避免正则替换造成意外范围扩大。
        if old_string not in original:
            return ToolResult(content=f"old_string not found in {path}", success=False, error="old_string_not_found")

        path.write_text(original.replace(old_string, new_string, 1), encoding="utf-8")
        return ToolResult(content=f"Edited {path}")

    def _multi_replace(self, path: Path, original: str, edits: list[dict[str, str]]) -> ToolResult:
        if not edits:
            return ToolResult(content="edits must not be empty", success=False, error="empty_edits")
        for index, edit in enumerate(edits):
            old = edit.get("old", "")
            if not old:
                return ToolResult(content=f"edits[{index}].old must not be empty", success=False, error="empty_old_string")
            count = original.count(old)
            if count != 1:
                return ToolResult(
                    content=f"edits[{index}].old must match exactly once; found {count}",
                    success=False,
                    error="old_string_match_count",
                    metadata={"index": index, "match_count": count},
                )

        updated = original
        for edit in edits:
            updated = updated.replace(edit["old"], edit.get("new", ""), 1)
        path.write_text(updated, encoding="utf-8")
        return ToolResult(content=f"Edited {path}", metadata={"edit_count": len(edits), "mode": "multi_replace"})
