"""内置 glob 路径枚举工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.buildin.file_filter import should_skip_for_search


class GlobTool(Tool):
    """列出匹配 glob 模式的文件和目录。"""

    name = "glob"
    description = "List files and directories matching a glob pattern."

    def input_schema(self) -> dict[str, Any]:
        """返回 glob 搜索的参数 schema。"""
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, for example '**/*.py'."},
                "path": {"type": "string", "description": "Root directory to search from."},
                "limit": {"type": "integer", "description": "Maximum number of matches to return."},
            },
            "required": ["pattern"],
        }

    async def execute(self, pattern: str, path: str = ".", limit: int = 200) -> ToolResult:
        """返回匹配路径，并跳过噪声生成文件。"""
        root = Path(path).expanduser()
        if not root.exists():
            return ToolResult(content=f"Path not found: {root}", success=False, error="path_not_found")

        matches: list[str] = []
        for match in sorted(root.glob(pattern)):
            # 文件会过滤二进制和缓存目录；目录保留，便于 Agent 观察结构。
            if match.is_file() and should_skip_for_search(match):
                continue
            matches.append(str(match))
            if len(matches) >= limit:
                break
        return ToolResult(content="\n".join(matches) or "(no matches)", metadata={"count": len(matches)})
