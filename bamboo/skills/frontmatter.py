"""解析 Bamboo Skill 的 YAML frontmatter。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class SkillFrontmatterError(ValueError):
    """表示 `SKILL.md` frontmatter 缺失或格式非法。"""


@dataclass(frozen=True, slots=True)
class ParsedSkillMarkdown:
    """保存 `SKILL.md` 解析结果。"""

    frontmatter: dict[str, Any]
    body: str


def parse_skill_markdown(content: str) -> ParsedSkillMarkdown:
    """解析带 YAML frontmatter 的 Skill Markdown。"""
    if not content.startswith("---\n"):
        raise SkillFrontmatterError("SKILL.md must start with YAML frontmatter")

    end_marker = "\n---\n"
    end = content.find(end_marker, 4)
    if end == -1:
        raise SkillFrontmatterError("SKILL.md frontmatter must be closed by ---")

    raw_frontmatter = content[4:end]
    body = content[end + len(end_marker) :]
    try:
        parsed = yaml.safe_load(raw_frontmatter) or {}
    except yaml.YAMLError as exc:
        raise SkillFrontmatterError(f"Invalid YAML frontmatter: {exc}") from exc

    if not isinstance(parsed, dict):
        raise SkillFrontmatterError("SKILL.md frontmatter must be a mapping")
    return ParsedSkillMarkdown(frontmatter=parsed, body=body.strip())


def read_skill_markdown(path: Path) -> ParsedSkillMarkdown:
    """读取并解析 `SKILL.md`。"""
    return parse_skill_markdown(path.read_text(encoding="utf-8"))
