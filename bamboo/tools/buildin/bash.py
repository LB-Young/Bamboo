"""保守的内置 shell 命令工具。

该工具用于当前框架的基础命令执行能力。它不是完整沙箱，
但会拒绝明显危险命令、限制超时并截断输出。
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult


MAX_OUTPUT_BYTES = 512 * 1024

DANGEROUS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|\s)rm\s+-[^\n]*r[^\n]*f\b"),
    re.compile(r"(^|\s)sudo\b"),
    re.compile(r"(^|\s)mkfs\b"),
    re.compile(r"(^|\s)dd\s+"),
    re.compile(r"(^|\s):\(\)\s*\{"),
    re.compile(r"curl\b[^\n|;]*\|\s*(sh|bash)\b"),
    re.compile(r"wget\b[^\n|;]*\|\s*(sh|bash)\b"),
)


class BashTool(Tool):
    """执行 shell 命令，并进行保守安全检查。"""

    name = "bash"
    description = "Execute a shell command with timeout and dangerous-command rejection."
    risk_level = "execute"
    tags = ("shell", "execute")

    def __init__(self, *, default_timeout: int = 30, max_timeout: int = 120) -> None:
        """初始化命令超时限制。"""
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout

    def input_schema(self) -> dict[str, Any]:
        """返回 shell 执行参数 schema。"""
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
                "cwd": {"type": "string", "description": "Working directory."},
                "timeout": {"type": "integer", "description": "Timeout in seconds."},
            },
            "required": ["command"],
        }

    async def execute(self, command: str, cwd: str = ".", timeout: int | None = None) -> ToolResult:
        """运行 shell 命令，并返回 stdout、stderr 和退出码。"""
        blocked_reason = self._blocked_reason(command)
        if blocked_reason:
            return ToolResult(content=f"Command blocked: {blocked_reason}", success=False, error="command_blocked")

        workdir = Path(cwd).expanduser()
        if not workdir.exists() or not workdir.is_dir():
            return ToolResult(content=f"Invalid cwd: {workdir}", success=False, error="invalid_cwd")

        exec_timeout = min(timeout or self.default_timeout, self.max_timeout)
        # 使用 asyncio 子进程，便于后续接入取消、超时和流式输出。
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=exec_timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return ToolResult(content=f"Command timed out after {exec_timeout}s", success=False, error="timeout")

        output = self._truncate(stdout.decode("utf-8", errors="replace"))
        error_output = self._truncate(stderr.decode("utf-8", errors="replace"))
        content = "\n".join(
            part
            for part in [
                f"returncode: {process.returncode}",
                f"stdout:\n{output}" if output else "stdout:",
                f"stderr:\n{error_output}" if error_output else "stderr:",
            ]
            if part
        )
        return ToolResult(content=content, success=process.returncode == 0, error=error_output)

    def _blocked_reason(self, command: str) -> str:
        """返回命令被拒绝的原因；空字符串表示允许执行。"""
        normalized = command.strip()
        if not normalized:
            return "empty command"
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(normalized):
                return f"matches dangerous pattern: {pattern.pattern}"
        return ""

    def _truncate(self, content: str) -> str:
        """把命令输出截断到固定字节上限。"""
        encoded = content.encode("utf-8", errors="replace")
        if len(encoded) <= MAX_OUTPUT_BYTES:
            return content
        return encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace") + "\n[output truncated]"
