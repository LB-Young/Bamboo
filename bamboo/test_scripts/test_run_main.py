"""测试脚本：直接调用 bamboo.run.main。

用途：
    python bamboo/test_scripts/test_run_main.py

该脚本绕过 Typer 命令解析，直接进入 run.py 的 main 函数，适合本地断点调试。
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bamboo.helpers.constant import SessionMode  # noqa: E402
from bamboo.run import main  # noqa: E402


def run_main_test() -> None:
    """调用 bamboo.run.main，触发当前 mock Agent 主流程。"""
    main(
        message="请介绍一下自己有什么能力",
        project=PROJECT_ROOT,
        model=None,
        provider=None,
        permission=None,
        no_stream=False,
        yes_all=False,
        session_mode=SessionMode.chat,
    )


if __name__ == "__main__":
    run_main_test()
