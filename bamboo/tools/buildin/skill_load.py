"""内置 Skill 加载工具。"""

from __future__ import annotations

from typing import Any

from bamboo.skills import SkillRegistry, create_skill_registry
from bamboo.tools.buildin.base import Tool, ToolResult


class SkillLoadTool(Tool):
    """按名称加载完整 Skill 指令和可选资源。"""

    name = "skill_load"
    description = "Load a Bamboo skill's full instructions before following its workflow."

    def __init__(self, *, skill_registry: SkillRegistry | None = None) -> None:
        """初始化 Skill 加载工具。"""
        self.skill_registry = skill_registry

    def input_schema(self) -> dict[str, Any]:
        """返回 Skill 加载参数 schema。"""
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name to load."},
                "include_experiences": {
                    "type": "boolean",
                    "description": "Whether to include experiences/README.md when available.",
                },
                "references": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional reference file names under the skill's references directory.",
                },
            },
            "required": ["name"],
        }

    async def execute(
        self,
        name: str,
        include_experiences: bool = True,
        references: list[str] | None = None,
    ) -> ToolResult:
        """读取 Skill 内容并返回给 Agent。"""
        registry = self.skill_registry or create_skill_registry()
        try:
            content = registry.load_skill_content(
                name,
                include_experiences=include_experiences,
                references=references or [],
            )
        except Exception as exc:
            return ToolResult(content=f"Failed to load skill `{name}`: {exc}", success=False, error=str(exc))
        return ToolResult(content=content, metadata={"skill_name": name})
