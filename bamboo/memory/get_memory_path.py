"""Bamboo memory 目录解析工具。"""

from __future__ import annotations

import os
import platform
from datetime import datetime
from pathlib import Path


def get_memory_dir() -> Path:
    """返回 Bamboo memory 根目录。"""
    if platform.system() == "Windows":
        base = Path(os.environ.get("USERPROFILE", Path.home()))
    else:
        base = Path.home()
    return base / ".bamboo" / "memory"


def get_memory_dir_name(project_path: str | Path) -> str:
    """根据项目路径生成稳定的 memory 目录名。"""
    project = Path(project_path).expanduser()
    return project.name or "default"


def get_project_memory_path(project_path: str | Path) -> Path:
    """返回项目级 session 的 memory 目录。"""
    return get_memory_dir() / "projects" / get_memory_dir_name(project_path)


def get_date_memory_path() -> Path:
    """返回按日期归档的 chat session memory 目录。"""
    return get_memory_dir() / "dates" / datetime.now().strftime("%Y-%m-%d")
