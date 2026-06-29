"""创建 Bamboo Skill 及其状态文件。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from bamboo.skills.frontmatter import read_skill_markdown
from bamboo.skills.models import SkillDefinition, SkillIndex, SkillUsageEvent
from bamboo.skills.store import SkillStore, utc_now
from bamboo.skills.validator import SKILL_NAME_RE, SkillValidator
from bamboo.userspace.userspace import get_user_skills_dir


@dataclass(frozen=True, slots=True)
class SkillCreateResult:
    """保存 Skill 创建结果。"""

    name: str
    source_path: Path
    state_path: Path
    status: str


class SkillCreator:
    """负责生成 Skill 源目录和完整状态文件。"""

    def __init__(
        self,
        *,
        skills_dir: Path | None = None,
        store: SkillStore | None = None,
        validator: SkillValidator | None = None,
    ) -> None:
        """初始化 Skill 创建器。"""
        self.skills_dir = skills_dir or get_user_skills_dir()
        self.store = store or SkillStore()
        self.validator = validator or SkillValidator()

    def create(
        self,
        name: str,
        *,
        description: str = "",
        overwrite: bool = False,
    ) -> SkillCreateResult:
        """创建一个新的用户 Skill。"""
        normalized_name = name.strip().lower()
        if not SKILL_NAME_RE.match(normalized_name):
            raise ValueError("Skill name must use lowercase letters, digits, and hyphens")

        skill_dir = self.skills_dir / normalized_name
        if skill_dir.exists() and not overwrite:
            raise FileExistsError(f"Skill already exists: {skill_dir}")

        skill_dir.mkdir(parents=True, exist_ok=True)
        for dirname in ("scripts", "references", "assets", "experiences"):
            (skill_dir / dirname).mkdir(exist_ok=True)

        skill_description = description or f"{normalized_name} workflow skill."
        self._write_default_skill_md(skill_dir, normalized_name, skill_description, overwrite=overwrite)
        self._write_default_config(skill_dir, normalized_name, overwrite=overwrite)
        self._write_default_experiences(skill_dir, normalized_name, overwrite=overwrite)

        definition = load_skill_definition(skill_dir, source="user")
        state = self.store.create_state(normalized_name, status="draft", health="unknown")
        self.store.save_index(build_skill_index(definition))
        validation = self.validator.validate(definition)
        self.store.save_validation(normalized_name, validation)
        self.store.append_usage(SkillUsageEvent(ts=utc_now(), event="created", skill_name=normalized_name))
        self.store.append_usage(SkillUsageEvent(ts=utc_now(), event="validated", skill_name=normalized_name))

        final_state = self.store.load_state(normalized_name) or state
        return SkillCreateResult(
            name=normalized_name,
            source_path=skill_dir,
            state_path=self.store.skill_dir(normalized_name),
            status=final_state.status,
        )

    def _write_default_skill_md(self, skill_dir: Path, name: str, description: str, *, overwrite: bool) -> None:
        path = skill_dir / "SKILL.md"
        if path.exists() and not overwrite:
            return
        content = f"""---
name: {name}
description: "{description}"
user-invocable: true
load-experiences: true
metadata:
  bamboo:
    emoji: "🔧"
---

# {name}

## When to Use

Use this skill when the task matches this reusable workflow.

Do not use this skill for unrelated general tasks.

## Workflow

1. Understand the user's request and decide whether this skill applies.
2. Load only the references needed for the task.
3. Use bundled scripts or assets when they are present.
4. Complete the task and record useful lessons in `experiences/README.md` when appropriate.
"""
        path.write_text(content, encoding="utf-8")

    def _write_default_config(self, skill_dir: Path, name: str, *, overwrite: bool) -> None:
        path = skill_dir / "config.yaml"
        if path.exists() and not overwrite:
            return
        data = {
            "schema_version": 1,
            "name": name,
            "enabled": True,
            "user_invocable": True,
            "load_experiences": True,
            "load_policy": {
                "auto_select": True,
                "max_references": 3,
                "max_tokens": 6000,
            },
            "requirements": {
                "bins": [],
                "env": [],
                "python_packages": [],
            },
            "permissions": {
                "can_run_commands": True,
                "can_edit_files": True,
                "can_access_network": False,
            },
        }
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def _write_default_experiences(self, skill_dir: Path, name: str, *, overwrite: bool) -> None:
        path = skill_dir / "experiences" / "README.md"
        if path.exists() and not overwrite:
            return
        path.write_text(
            f"# {name} Experiences\n\nRecord lessons learned while using this skill.\n",
            encoding="utf-8",
        )


def load_skill_definition(source_path: Path, *, source: str) -> SkillDefinition:
    """从目录读取 Skill 定义。"""
    parsed = read_skill_markdown(source_path / "SKILL.md")
    frontmatter = parsed.frontmatter
    name = str(frontmatter.get("name", "")).strip()
    description = str(frontmatter.get("description", "")).strip()
    user_invocable = bool(frontmatter.get("user-invocable", frontmatter.get("user_invocable", True)))
    load_experiences = bool(frontmatter.get("load-experiences", frontmatter.get("load_experiences", True)))
    return SkillDefinition(
        name=name,
        description=description,
        source_path=str(source_path),
        source=source,
        frontmatter=frontmatter,
        body=parsed.body,
        user_invocable=user_invocable,
        load_experiences=load_experiences,
    )


def build_skill_index(definition: SkillDefinition) -> SkillIndex:
    """根据 Skill 定义构建索引缓存。"""
    import hashlib

    source_path = Path(definition.source_path)
    skill_md_path = source_path / "SKILL.md"
    content = skill_md_path.read_bytes()
    resources = {
        dirname: _relative_files(source_path / dirname, source_path)
        for dirname in ("scripts", "references", "assets", "experiences")
    }
    triggers = _extract_triggers(definition)
    return SkillIndex(
        schema_version=1,
        name=definition.name,
        description=definition.description,
        source_path=definition.source_path,
        source=definition.source,
        skill_md_sha256=hashlib.sha256(content).hexdigest(),
        skill_md_mtime=skill_md_path.stat().st_mtime,
        estimated_tokens=max(1, len(skill_md_path.read_text(encoding="utf-8")) // 4),
        resources=resources,
        triggers=triggers,
        indexed_at=utc_now(),
    )


def _relative_files(root: Path, base: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(str(path.relative_to(base)) for path in root.rglob("*") if path.is_file())


def _extract_triggers(definition: SkillDefinition) -> list[str]:
    metadata = definition.frontmatter.get("metadata", {})
    if isinstance(metadata, dict):
        bamboo = metadata.get("bamboo", {})
        if isinstance(bamboo, dict):
            triggers = bamboo.get("triggers", [])
            if isinstance(triggers, list):
                return [str(trigger) for trigger in triggers]
    words = [part.strip(".,:;()[]{}").lower() for part in definition.description.split()]
    return sorted({word for word in words if len(word) > 3})[:12]
