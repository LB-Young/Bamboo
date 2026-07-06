"""Bamboo 系统提示词构建器。

该模块负责把 markdown 形式的静态提示词片段、运行环境信息和项目
指令文件组装成一次会话使用的 system prompt。
"""

from __future__ import annotations

import datetime
import hashlib
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from bamboo.helpers.constant import SessionMode

PromptMode = Literal["project", "chat"]

PROMPT_DIR = Path(__file__).resolve().parent
PROMPT_SECTION_DIRS: dict[PromptMode, tuple[str, ...]] = {
    "project": ("project", "shared"),
    "chat": ("chat", "shared"),
}
PROJECT_MARKERS = (
    ".git",
    "AGENTS.md",
    "CLAUDE.md",
    "BAMBOO.md",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Cargo.toml",
)
PROJECT_INSTRUCTION_FILES = ("BAMBOO.md", "AGENTS.md", "CLAUDE.md")


@dataclass(frozen=True, slots=True)
class PromptSection:
    """A debuggable section of a rendered prompt."""

    name: str
    content: str
    source: str
    priority: int = 100
    cacheable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """Return a stable hash of this section's content."""
        return hash_prompt_text(self.content)

    def to_metadata(self) -> dict[str, Any]:
        """Return section metadata without full prompt content."""
        return {
            "name": self.name,
            "source": self.source,
            "priority": self.priority,
            "cacheable": self.cacheable,
            "content_hash": self.content_hash,
            "content_chars": len(self.content),
            "metadata": dict(self.metadata),
        }


def resolve_prompt_mode(session_mode: SessionMode | str, project_root: Path) -> PromptMode:
    """根据会话模式和项目目录特征选择 project 或 chat system prompt。"""
    mode = getattr(session_mode, "value", session_mode) or SessionMode.chat.value
    if mode == SessionMode.project.value:
        return "project"
    if mode == SessionMode.chat.value:
        return "chat"
    if mode == SessionMode.auto.value and _looks_like_project(project_root):
        return "project"
    return "chat"


def build_system_prompt(
    *,
    session_mode: SessionMode | str,
    project_root: Path,
    memory_dir: Path,
    model: str = "",
    provider: str = "",
) -> str:
    """便捷函数：创建默认构建器并返回完整 system prompt。"""
    prompt_mode = resolve_prompt_mode(session_mode, project_root)
    return SystemPromptBuilder(prompt_mode=prompt_mode).build(
        project_root=project_root,
        memory_dir=memory_dir,
        model=model,
        provider=provider,
    )


def build_system_prompt_sections(
    *,
    session_mode: SessionMode | str,
    project_root: Path,
    memory_dir: Path,
    model: str = "",
    provider: str = "",
) -> list[PromptSection]:
    """便捷函数：创建默认构建器并返回 prompt section 列表。"""
    prompt_mode = resolve_prompt_mode(session_mode, project_root)
    return SystemPromptBuilder(prompt_mode=prompt_mode).build_sections(
        project_root=project_root,
        memory_dir=memory_dir,
        model=model,
        provider=provider,
    )


def render_prompt_sections(sections: list[PromptSection]) -> str:
    """按 priority/name/source 稳定渲染 prompt section。"""
    ordered = sorted(sections, key=lambda section: (section.priority, section.name, section.source))
    return "\n\n".join(section.content.strip() for section in ordered if section.content.strip())


def hash_prompt_text(content: str) -> str:
    """返回 prompt 文本的稳定 SHA-256 hash。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SystemPromptBuilder:
    """按固定顺序组装 Bamboo system prompt。"""

    prompt_mode: PromptMode

    def build(self, *, project_root: Path, memory_dir: Path, model: str = "", provider: str = "") -> str:
        """组装完整 system prompt 文本。"""
        return render_prompt_sections(
            self.build_sections(
                project_root=project_root,
                memory_dir=memory_dir,
                model=model,
                provider=provider,
            )
        )

    def build_sections(
        self,
        *,
        project_root: Path,
        memory_dir: Path,
        model: str = "",
        provider: str = "",
    ) -> list[PromptSection]:
        """组装完整 system prompt section 列表。"""
        sections = [
            *_read_prompt_sections(self.prompt_mode),
            PromptSection(
                name="runtime-environment",
                source="runtime",
                priority=900,
                cacheable=False,
                content=_build_environment_section(
                    prompt_mode=self.prompt_mode,
                    project_root=project_root,
                    memory_dir=memory_dir,
                    model=model,
                    provider=provider,
                ),
                metadata={"prompt_mode": self.prompt_mode},
            ),
        ]
        if self.prompt_mode == "project":
            sections.extend(_read_project_instruction_sections(project_root))
        return sections


def _read_prompt_sections(prompt_mode: PromptMode) -> list[PromptSection]:
    """按模式读取多个 markdown prompt 片段。"""
    sections: list[PromptSection] = []
    for dir_index, section_dir_name in enumerate(PROMPT_SECTION_DIRS[prompt_mode]):
        section_dir = _resolve_prompt_section_dir(section_dir_name)
        if not section_dir.is_dir():
            continue
        base_priority = 100 + (dir_index * 100)
        for file_index, section_path in enumerate(sorted(section_dir.glob("*.md"))):
            content = section_path.read_text(encoding="utf-8").strip()
            if content:
                sections.append(
                    PromptSection(
                        name=section_path.stem,
                        source=str(section_path),
                        priority=base_priority + file_index,
                        cacheable=True,
                        content=content,
                        metadata={"prompt_mode": prompt_mode, "section_dir": section_dir_name},
                    )
                )
    return sections


def read_provider_prompt_section_objects(prompt_profile: str) -> list[PromptSection]:
    """按模型 prompt_profile 读取 provider 专用 prompt section 对象。"""
    normalized_profile = prompt_profile.strip().lower()
    if not normalized_profile:
        return []
    section_dir = _resolve_prompt_section_dir(f"provider/{normalized_profile}")
    if not section_dir.is_dir():
        return []
    sections: list[PromptSection] = []
    for file_index, section_path in enumerate(sorted(section_dir.glob("*.md"))):
        content = section_path.read_text(encoding="utf-8").strip()
        if content:
            sections.append(
                PromptSection(
                    name=f"provider-{normalized_profile}-{section_path.stem}",
                    source=str(section_path),
                    priority=500 + file_index,
                    cacheable=True,
                    content=content,
                    metadata={"prompt_profile": normalized_profile},
                )
            )
    return sections


def read_provider_prompt_sections(prompt_profile: str) -> list[str]:
    """按模型 prompt_profile 读取 provider 专用 prompt 片段。"""
    return [section.content for section in read_provider_prompt_section_objects(prompt_profile)]


def _resolve_prompt_section_dir(section_dir_name: str) -> Path:
    """优先返回用户空间中的 prompt section 目录，否则回退到包内默认目录。"""
    from bamboo.userspace.userspace import get_configs_dir

    user_section_dir = get_configs_dir() / "prompts" / section_dir_name
    if user_section_dir.is_dir():
        return user_section_dir
    return PROMPT_DIR / section_dir_name


def _looks_like_project(project_root: Path) -> bool:
    """判断目录是否具有常见工程项目特征。"""
    return any((project_root / marker).exists() for marker in PROJECT_MARKERS)


def _build_environment_section(
    *,
    prompt_mode: PromptMode,
    project_root: Path,
    memory_dir: Path,
    model: str,
    provider: str,
) -> str:
    """生成当前会话的运行环境信息。"""
    shell = os.environ.get("SHELL", "unknown")
    today = datetime.date.today().isoformat()
    lines = [
        "# Runtime Environment",
        f"- Prompt Mode: {prompt_mode}",
        f"- OS: {platform.system()} {platform.release()} ({platform.machine()})",
        f"- Shell: `{shell}`",
        f"- Working Directory: `{Path.cwd()}`",
        f"- Project Root: `{project_root}`",
        f"- Memory Directory: `{memory_dir}`",
        f"- Today's Date: {today}",
    ]
    if model:
        lines.append(f"- Model: `{model}`")
    if provider:
        lines.append(f"- Provider: `{provider}`")
    return "\n".join(lines)


def _read_project_instruction_sections(project_root: Path) -> list[PromptSection]:
    """读取项目根目录下约定的 Agent 指令文件。"""
    instruction_sections: list[str] = []
    sources: list[str] = []
    for file_name in PROJECT_INSTRUCTION_FILES:
        instruction_path = project_root / file_name
        if instruction_path.is_file():
            content = instruction_path.read_text(encoding="utf-8").strip()
            if content:
                instruction_sections.append(f"## {file_name}\n\n{content}")
                sources.append(str(instruction_path))
    if not instruction_sections:
        return []
    return [
        PromptSection(
            name="project-instructions",
            source=", ".join(sources),
            priority=1000,
            cacheable=False,
            content="# Project Instructions\n\n" + "\n\n".join(instruction_sections),
            metadata={"files": sources},
        )
    ]
