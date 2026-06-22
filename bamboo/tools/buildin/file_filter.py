"""内置工具共用的文件过滤逻辑。

读取和搜索工具会通过这些函数跳过二进制文件、缓存目录和高噪声路径，
避免把无意义内容塞进 Agent 上下文。
"""

from __future__ import annotations

from pathlib import Path


BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".7z",
        ".a",
        ".avi",
        ".bin",
        ".bmp",
        ".bz2",
        ".class",
        ".db",
        ".dll",
        ".doc",
        ".docx",
        ".dylib",
        ".egg",
        ".exe",
        ".gif",
        ".gz",
        ".ico",
        ".jar",
        ".jpeg",
        ".jpg",
        ".lock",
        ".mov",
        ".mp3",
        ".mp4",
        ".npy",
        ".o",
        ".pdf",
        ".pkl",
        ".png",
        ".ppt",
        ".pptx",
        ".pyc",
        ".pyd",
        ".pyo",
        ".rar",
        ".so",
        ".sqlite",
        ".sqlite3",
        ".tar",
        ".tif",
        ".tiff",
        ".webm",
        ".webp",
        ".whl",
        ".xls",
        ".xlsx",
        ".xz",
        ".zip",
    }
)

NOISY_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "chroma_db",
        "dist",
        "env",
        "memory",
        "node_modules",
        "site-packages",
        "sessions",
        "venv",
        "vector_db",
    }
)


def is_binary_path(path: Path) -> bool:
    """判断路径是否像二进制文件或生成产物。"""
    return path.suffix.lower() in BINARY_EXTENSIONS or path.name == ".DS_Store"


def is_noisy_path(path: Path) -> bool:
    """判断路径是否位于高噪声目录中。"""
    return bool(set(path.parts) & NOISY_DIRS)


def should_skip_for_read(path: Path) -> tuple[bool, str]:
    """判断 ReadTool 是否应该拒绝读取该路径。"""
    if is_binary_path(path):
        return True, f"Refusing to read binary or generated file: {path}"
    if path.is_file() and binary_sniff(path):
        return True, f"Refusing to read probable binary file: {path}"
    return False, ""


def should_skip_for_search(path: Path) -> bool:
    """判断搜索类工具是否应该跳过该路径。"""
    return is_binary_path(path) or is_noisy_path(path)


def binary_sniff(path: Path, sample_bytes: int = 512) -> bool:
    """通过 NULL 字节嗅探疑似二进制文件。"""
    try:
        return b"\x00" in path.read_bytes()[:sample_bytes]
    except OSError:
        return False
