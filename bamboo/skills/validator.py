"""Skill 校验逻辑。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from bamboo.helpers.config import load_builtin_skill_config
from bamboo.skills.models import SkillDefinition, SkillValidationResult
from bamboo.skills.store import utc_now

SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$")


class SkillValidator:
    """校验 Skill 定义、配置和本地依赖。"""

    def validate(self, definition: SkillDefinition) -> SkillValidationResult:
        """返回指定 Skill 的校验结果。"""
        errors: list[str] = []
        warnings: list[str] = []
        checks: dict[str, Any] = {}

        source_path = Path(definition.source_path)
        skill_md_path = source_path / "SKILL.md"
        config_path = source_path / "config.yaml"

        checks["skill_md_exists"] = "ok" if skill_md_path.is_file() else "error"
        if not skill_md_path.is_file():
            errors.append("SKILL.md is missing")

        checks["name_present"] = "ok" if definition.name else "error"
        if not definition.name:
            errors.append("frontmatter.name is required")
        elif not SKILL_NAME_RE.match(definition.name):
            checks["name_format"] = "error"
            errors.append("frontmatter.name must use lowercase letters, digits, and hyphens")
        else:
            checks["name_format"] = "ok"

        checks["name_matches_directory"] = "ok" if source_path.name == definition.name else "warning"
        if source_path.name != definition.name:
            warnings.append("skill directory name should match frontmatter.name")

        checks["description_present"] = "ok" if definition.description else "error"
        if not definition.description:
            errors.append("frontmatter.description is required")
        elif len(definition.description) > 1024:
            checks["description_length"] = "error"
            errors.append("frontmatter.description must be 1024 characters or fewer")
        else:
            checks["description_length"] = "ok"

        metadata = definition.frontmatter.get("metadata", {})
        if metadata:
            if not isinstance(metadata, dict):
                checks["metadata"] = "error"
                errors.append("frontmatter.metadata must be a mapping")
            else:
                bamboo_metadata = metadata.get("bamboo", {})
                if bamboo_metadata:
                    if not isinstance(bamboo_metadata, dict):
                        checks["metadata.bamboo"] = "error"
                        errors.append("frontmatter.metadata.bamboo must be a mapping")
                    else:
                        tags = bamboo_metadata.get("tags", [])
                        if tags and (
                            not isinstance(tags, list)
                            or any(not isinstance(tag, str) or not tag.strip() for tag in tags)
                        ):
                            checks["metadata.bamboo.tags"] = "error"
                            errors.append("frontmatter.metadata.bamboo.tags must be a list of non-empty strings")
                        else:
                            checks["metadata.bamboo.tags"] = "ok"

        if definition.source == "buildin":
            config = load_builtin_skill_config(definition.name)
            checks["builtin_config"] = "ok" if config else "warning"
            if not config:
                warnings.append("built-in skill config is missing from skills_buildin.yaml")
            checks["config_yaml"] = "centralized"
        else:
            config = self._read_config(config_path, errors, warnings)
            checks["config_yaml"] = "ok" if config_path.is_file() else "warning"
            if not config_path.is_file():
                warnings.append("config.yaml is missing")

        requirement_checks = self._validate_requirements(config)
        checks["requirements"] = requirement_checks
        missing_bins = [name for name, status in requirement_checks.get("bins", {}).items() if status == "missing"]
        if missing_bins:
            warnings.append(f"required binaries missing: {', '.join(missing_bins)}")

        for dirname in ("scripts", "references", "assets", "experiences"):
            checks[f"{dirname}_dir"] = "ok" if (source_path / dirname).is_dir() else "missing"

        return SkillValidationResult(
            schema_version=1,
            validated_at=utc_now(),
            ok=not errors,
            errors=errors,
            warnings=warnings,
            checks=checks,
        )

    def _read_config(self, path: Path, errors: list[str], warnings: list[str]) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            errors.append(f"config.yaml is invalid YAML: {exc}")
            return {}
        if not isinstance(data, dict):
            errors.append("config.yaml must be a mapping")
            return {}
        config_name = data.get("name")
        if isinstance(config_name, str) and config_name != path.parent.name:
            warnings.append("config.yaml name should match skill directory name")
        return data

    def _validate_requirements(self, config: dict[str, Any]) -> dict[str, Any]:
        requirements = config.get("requirements", {})
        if not isinstance(requirements, dict):
            return {"error": "requirements must be a mapping"}

        bins = requirements.get("bins", [])
        if not isinstance(bins, list):
            return {"error": "requirements.bins must be a list"}
        return {
            "bins": {
                str(binary): "ok" if shutil.which(str(binary)) else "missing"
                for binary in bins
            }
        }
