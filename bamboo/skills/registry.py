"""Bamboo Skill 注册表。"""

from __future__ import annotations

from pathlib import Path

import yaml

from bamboo.skills.creator import build_skill_index, load_skill_definition
from bamboo.skills.frontmatter import SkillFrontmatterError
from bamboo.skills.models import SkillDefinition, SkillUsageEvent
from bamboo.skills.store import SkillStore, utc_now
from bamboo.skills.validator import SkillValidator
from bamboo.userspace.userspace import get_builtin_skills_dir, get_user_skills_dir

PACKAGE_BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent / "buildin"


class SkillRegistry:
    """扫描、索引并加载 Bamboo Skills。"""

    def __init__(
        self,
        *,
        skill_dirs: list[tuple[str, Path]] | None = None,
        store: SkillStore | None = None,
        validator: SkillValidator | None = None,
    ) -> None:
        """初始化 Skill 注册表。"""
        self.skill_dirs = skill_dirs or [
            ("buildin", PACKAGE_BUILTIN_SKILLS_DIR),
            ("buildin", get_builtin_skills_dir()),
            ("user", get_user_skills_dir()),
        ]
        self.store = store or SkillStore()
        self.validator = validator or SkillValidator()
        self._definitions: dict[str, SkillDefinition] = {}

    def refresh(self) -> None:
        """重新扫描所有 Skill 目录并更新索引状态。"""
        discovered: dict[str, SkillDefinition] = {}
        for source, root in self.skill_dirs:
            if not root.is_dir():
                continue
            for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
                if not (skill_dir / "SKILL.md").is_file():
                    continue
                try:
                    definition = load_skill_definition(skill_dir, source=source)
                except (OSError, SkillFrontmatterError, ValueError) as exc:
                    fallback_name = skill_dir.name
                    try:
                        state = self.store.load_state(fallback_name) or self.store.create_state(fallback_name)
                        state.status = "error"
                        state.health = "error"
                        state.last_error = str(exc)
                        self.store.save_state(state)
                    except OSError:
                        pass
                    continue
                if definition.name:
                    discovered[definition.name] = definition
                    self._sync_definition(definition)
        self._definitions = discovered

    def list(self, *, include_inactive: bool = False) -> list[SkillDefinition]:
        """返回已发现的 Skill 定义。"""
        if not self._definitions:
            self.refresh()
        definitions = []
        for definition in self._definitions.values():
            state = self.store.load_state(definition.name)
            if include_inactive or (state is not None and state.status == "active"):
                definitions.append(definition)
        return sorted(definitions, key=lambda item: item.name)

    def get(self, name: str, *, include_inactive: bool = False) -> SkillDefinition | None:
        """按名称获取 Skill 定义。"""
        if not self._definitions:
            self.refresh()
        definition = self._definitions.get(name)
        if definition is None:
            return None
        state = self.store.load_state(name)
        if include_inactive or (state is not None and state.status == "active"):
            return definition
        return None

    def render_catalog(self) -> str:
        """渲染可注入 prompt 的 Skill 摘要。"""
        rows = []
        for definition in self.list():
            state = self.store.load_state(definition.name)
            health = state.health if state is not None else "unknown"
            rows.append(f"- `{definition.name}` ({definition.source}, {health}): {definition.description}")
        if not rows:
            return ""
        return "\n".join(
            [
                "Use the `skill_load` tool to load a skill before following its full workflow.",
                *rows,
            ]
        )

    def load_skill_content(
        self,
        name: str,
        *,
        include_experiences: bool = True,
        references: list[str] | None = None,
    ) -> str:
        """读取完整 Skill 内容，并记录 loaded 事件。"""
        definition = self.get(name)
        if definition is None:
            raise KeyError(f"Skill is not active or does not exist: {name}")

        source_path = Path(definition.source_path)
        sections = [
            f"# Skill: {definition.name}",
            (source_path / "SKILL.md").read_text(encoding="utf-8"),
        ]
        if include_experiences and definition.load_experiences:
            experiences_path = source_path / "experiences" / "README.md"
            if experiences_path.is_file():
                sections.extend(["# Experiences", experiences_path.read_text(encoding="utf-8")])

        for reference in references or []:
            reference_path = (source_path / "references" / reference).resolve()
            references_root = (source_path / "references").resolve()
            try:
                reference_path.relative_to(references_root)
            except ValueError as exc:
                raise FileNotFoundError(f"Skill reference not found: {reference}") from exc
            if not reference_path.is_file():
                raise FileNotFoundError(f"Skill reference not found: {reference}")
            sections.extend([f"# Reference: {reference}", reference_path.read_text(encoding="utf-8")])

        content = "\n\n".join(section.strip() for section in sections if section.strip())
        self.store.append_usage(
            SkillUsageEvent(
                ts=utc_now(),
                event="loaded",
                skill_name=definition.name,
                tokens=max(1, len(content) // 4),
            )
        )
        return content

    def _sync_definition(self, definition: SkillDefinition) -> None:
        try:
            state = self.store.load_state(definition.name) or self.store.create_state(definition.name)
            validation = self.validator.validate(definition)
            self.store.save_validation(definition.name, validation)
            config_enabled = self._config_enabled(Path(definition.source_path))
            if state.status == "disabled" or not config_enabled:
                disabled_state = self.store.load_state(definition.name)
                if disabled_state is not None:
                    disabled_state.status = "disabled"
                    self.store.save_state(disabled_state)
            if validation.ok:
                self.store.save_index(build_skill_index(definition))
        except OSError:
            # Skill 状态存储不可写时保持注册表可构建，避免运行时初始化失败。
            return

    def _config_enabled(self, source_path: Path) -> bool:
        config_path = source_path / "config.yaml"
        if not config_path.is_file():
            return True
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return True
        if not isinstance(data, dict):
            return True
        enabled = data.get("enabled")
        return enabled if isinstance(enabled, bool) else True


def create_skill_registry() -> SkillRegistry:
    """创建默认 SkillRegistry 并立即扫描。"""
    registry = SkillRegistry()
    registry.refresh()
    return registry
