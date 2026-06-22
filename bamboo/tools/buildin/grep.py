"""内置正则内容搜索工具。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.buildin.file_filter import should_skip_for_search


class GrepTool(Tool):
    """使用 Python 正则表达式搜索文本文件。"""

    name = "grep"
    description = "Search for a regex pattern in text files."

    def input_schema(self) -> dict[str, Any]:
        """返回内容搜索的参数 schema。"""
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Python regex pattern to search for."},
                "path": {"type": "string", "description": "Directory or file to search."},
                "glob": {"type": "string", "description": "Optional file glob, for example '*.py'."},
                "context": {"type": "integer", "description": "Context lines around each match."},
                "limit": {"type": "integer", "description": "Maximum number of matches."},
            },
            "required": ["pattern"],
        }

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        glob: str = "*",
        context: int = 2,
        limit: int = 100,
    ) -> ToolResult:
        """搜索文件并返回带行号的片段。"""
        root = Path(path).expanduser()
        if not root.exists():
            return ToolResult(content=f"Path not found: {root}", success=False, error="path_not_found")

        regex = re.compile(pattern)
        files = [root] if root.is_file() else [candidate for candidate in root.rglob(glob) if candidate.is_file()]
        results: list[str] = []

        for file_path in files:
            if should_skip_for_search(file_path):
                continue
            try:
                # 搜索工具应尽量容错，单个文件读取失败不影响整体搜索。
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue

            for index, line in enumerate(lines):
                if regex.search(line) is None:
                    continue
                first = max(0, index - context)
                last = min(len(lines), index + context + 1)
                snippet = "\n".join(f"{line_no + 1}: {lines[line_no]}" for line_no in range(first, last))
                results.append(f"{file_path}:{index + 1}\n{snippet}")
                if len(results) >= limit:
                    return ToolResult(content="\n\n".join(results), metadata={"count": len(results)})

        return ToolResult(content="\n\n".join(results) or "(no matches)", metadata={"count": len(results)})
