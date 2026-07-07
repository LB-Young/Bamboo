"""用户空间初始化工具。

该模块负责准备 `~/.bamboo` 下的配置、工具、技能、日志、工作区等目录。
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from bamboo.memory.manager import MemoryManager

dirs: list[str] = [
    "configs",                  # 配置目录
    "configs/mcp.d",            # Plugin 安装的 MCP 配置片段
    "prompts",                  # 可编辑系统提示词模板
    "buildin_tools",            # 内建 Tool（安装时从包内复制）
    "tools",                    # 用户安装的 Tool / Agent 创建的 Skill
    "buildin_skills",           # 内建 Skill（安装时从包内复制）
    "skills",                   # 用户安装的 Skill / Agent 创建的 Skill
    "buildin_subagents",        # 内建的 Subagent
    "subagents",                # 用户安装的 Subagent
    "buildin_workflows",        # 内建工作流（安装时从包内复制）
    "workflows",                # 用户定义的工作流
    "storage",                  # 结构化存储根
    "storage/projects",         # 项目级存储
    "storage/dates",            # 日期级存储
    "storage/skills",           # Skill 状态、索引、校验和使用记录
    "storage/plugins",          # Plugin lock 和审计记录
    "memory",                   # 全局记忆
    "tasks",                    # 任务队列
    "cron",                     # Cron job 配置和调度状态
    "logs",                     # 日志
    "plugins",                  # Plugin 安装隔离区
    "plugins/quarantine",       # Plugin quarantine
    "workspace",                # 默认工作区
    "workspace/tmp",            # 临时文件
]


@dataclass(frozen=True, slots=True)
class UserspaceLayout:
    """保存 Bamboo 用户空间根目录，供 CLI 初始化结果展示。"""

    root: Path

def get_configs_dir() -> Path:
    """获取用户本地 .bamboo 根目录。"""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("USERPROFILE", Path.home()))
    else:
        base = Path.home()
    return base / ".bamboo"


def get_userspace_dir() -> Path:
    """获取 Bamboo 用户空间根目录。"""
    return get_configs_dir()


def get_user_skills_dir() -> Path:
    """获取用户安装或 Agent 创建的 Skill 目录。"""
    return get_userspace_dir() / "skills"


def get_builtin_skills_dir() -> Path:
    """获取用户空间中的内置 Skill 镜像目录。"""
    return get_userspace_dir() / "buildin_skills"


def get_skill_storage_dir() -> Path:
    """获取 Skill 运行状态存储目录。"""
    return get_userspace_dir() / "storage" / "skills"


def ensure_userspace(*, overwrite: bool = False) -> UserspaceLayout:
    """确保 Bamboo 用户空间目录存在，并复制内置资源。"""
    bamboo_root_dir = get_configs_dir()
    if overwrite and bamboo_root_dir.exists():
        shutil.rmtree(bamboo_root_dir)

    for subdir in dirs:
        target = bamboo_root_dir / subdir
        target.mkdir(parents=True, exist_ok=True)

        if subdir in ["configs", "prompts", "buildin_tools", "buildin_skills", "buildin_subagents", "buildin_workflows"]:
            copy_builtin_info(subdir, target)
        else:
            logger.info(f"Ensured directory: {target}")
    MemoryManager(memory_root=bamboo_root_dir / "memory").ensure_base_knowledge_templates()
    _ensure_cron_jobs_template(bamboo_root_dir)
    return UserspaceLayout(root=bamboo_root_dir)


def copy_builtin_info(subdir: str, target_dir: Path) -> None:
    """只复制用户空间中尚不存在的内置文件，避免覆盖用户配置。"""
    package_root = Path(__file__).resolve().parent.parent
    src_dir = package_root / subdir
    if subdir == "buildin_skills":
        src_dir = package_root / "skills" / "buildin"
    if subdir == "buildin_subagents":
        src_dir = package_root / "subagents" / "buildin"
    if subdir == "buildin_workflows":
        src_dir = package_root / "workflows" / "buildin"
    if src_dir.exists():
        for source_path in src_dir.rglob("*"):
            if subdir == "prompts" and source_path.is_file() and source_path.suffix != ".md":
                continue
            relative_path = source_path.relative_to(src_dir)
            destination_path = target_dir / relative_path
            if source_path.is_dir():
                destination_path.mkdir(parents=True, exist_ok=True)
            elif not destination_path.exists():
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination_path)
        logger.info(f"Copied built-in {subdir} to {target_dir}")
    else:
        logger.warning(f"Built-in {subdir} not found in package.")


def _ensure_cron_jobs_template(bamboo_root_dir: Path) -> None:
    """Create the default cron jobs file without overwriting user jobs."""
    cron_jobs_path = bamboo_root_dir / "cron" / "jobs.yaml"
    if cron_jobs_path.exists():
        return
    cron_jobs_path.parent.mkdir(parents=True, exist_ok=True)
    cron_jobs_path.write_text(
        "# Bamboo cron jobs.\n"
        "# Start scheduler with: bamboo cron start\n"
        "# Run one tick with: bamboo cron tick\n"
        "jobs: []\n",
        encoding="utf-8",
    )
