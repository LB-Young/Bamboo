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

dirs: list[str] = [
    "configs",                  # 配置目录
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
    "memory",                   # 全局记忆
    "tasks",                    # 任务队列
    "logs",                     # 日志
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


def ensure_userspace() -> UserspaceLayout:
    """确保 Bamboo 用户空间目录存在，并复制内置资源。"""
    bamboo_root_dir = get_configs_dir()

    for subdir in dirs:
        target = bamboo_root_dir / subdir
        target.mkdir(parents=True, exist_ok=True)

        if subdir in ["configs", "prompts", "buildin_tools", "buildin_skills", "buildin_subagents", "buildin_workflows"]:
            copy_builtin_info(subdir, target)
        else:
            logger.info(f"Ensured directory: {target}")
    return UserspaceLayout(root=bamboo_root_dir)


def copy_builtin_info(subdir: str, target_dir: Path) -> None:
    """只复制用户空间中尚不存在的内置文件，避免覆盖用户配置。"""
    src_dir = Path(__file__).resolve().parent.parent / subdir
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
