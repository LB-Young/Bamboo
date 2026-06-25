"""Bamboo 系统提示词构建器。

该模块负责把 markdown 形式的静态提示词片段、运行环境信息和项目
指令文件组装成一次会话使用的 system prompt。
"""

from __future__ import annotations

import datetime
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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


@dataclass(frozen=True, slots=True)
class SystemPromptBuilder:
    """按固定顺序组装 Bamboo system prompt。"""

    prompt_mode: PromptMode

    def build(self, *, project_root: Path, memory_dir: Path, model: str = "", provider: str = "") -> str:
        """组装完整 system prompt 文本。"""
        sections = [
            *_read_prompt_sections(self.prompt_mode),
            _build_environment_section(
                prompt_mode=self.prompt_mode,
                project_root=project_root,
                memory_dir=memory_dir,
                model=model,
                provider=provider,
            ),
        ]
        if self.prompt_mode == "project":
            project_instructions = _read_project_instructions(project_root)
            if project_instructions:
                sections.append(project_instructions)
        return "\n\n".join(section.strip() for section in sections if section.strip())


def _read_prompt_sections(prompt_mode: PromptMode) -> list[str]:
    """按模式读取多个 markdown prompt 片段。"""
    sections = []
    for section_dir_name in PROMPT_SECTION_DIRS[prompt_mode]:
        section_dir = _resolve_prompt_section_dir(section_dir_name)
        for section_path in sorted(section_dir.glob("*.md")):
            content = section_path.read_text(encoding="utf-8").strip()
            if content:
                sections.append(content)
    return sections


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


def _read_project_instructions(project_root: Path) -> str:
    """读取项目根目录下约定的 Agent 指令文件。"""
    instruction_sections = []
    for file_name in PROJECT_INSTRUCTION_FILES:
        instruction_path = project_root / file_name
        if instruction_path.is_file():
            content = instruction_path.read_text(encoding="utf-8").strip()
            if content:
                instruction_sections.append(f"## {file_name}\n\n{content}")
    if not instruction_sections:
        return ""
    return "# Project Instructions\n\n" + "\n\n".join(instruction_sections)
