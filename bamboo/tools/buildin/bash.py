"""保守的内置 shell 命令工具。

该工具用于当前框架的基础命令执行能力。它不是完整沙箱，
但会拒绝明显危险命令、限制超时并截断输出。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from bamboo.helpers.config import BambooConfig
from bamboo.security import SandboxConfig, inspect_command, run_sandboxed
from bamboo.tools.buildin.base import Tool, ToolResult


MAX_OUTPUT_BYTES = 512 * 1024


class BashTool(Tool):
    """执行 shell 命令，并进行保守安全检查。"""

    name = "bash"
    description = "Execute a shell command with timeout and dangerous-command rejection."
    risk_level = "execute"
    tags = ("shell", "execute")

    def __init__(
        self,
        *,
        default_timeout: int = 30,
        max_timeout: int = 120,
        sandbox_config: SandboxConfig | None = None,
    ) -> None:
        """初始化命令超时限制。"""
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout
        self.sandbox_config = sandbox_config

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
        security = inspect_command(command)
        if not security.allowed:
            return ToolResult(
                content=f"Command blocked: {security.reason}",
                success=False,
                error="command_blocked",
                metadata={"risk": security.risk.value, "requires_confirmation": security.requires_confirmation},
            )

        workdir = Path(cwd).expanduser()
        if not workdir.exists() or not workdir.is_dir():
            return ToolResult(content=f"Invalid cwd: {workdir}", success=False, error="invalid_cwd")

        exec_timeout = min(timeout or self.default_timeout, self.max_timeout)
        sandbox_config = self.sandbox_config if self.sandbox_config is not None else _load_sandbox_config()
        if sandbox_config.enabled:
            return await self._execute_sandboxed(
                command=command,
                workdir=workdir,
                timeout=exec_timeout,
                security_metadata={"risk": security.risk.value, "requires_confirmation": security.requires_confirmation},
                sandbox_config=sandbox_config,
            )

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
        return ToolResult(
            content=content,
            success=process.returncode == 0,
            error=error_output,
            metadata={"risk": security.risk.value, "requires_confirmation": security.requires_confirmation},
        )

    async def _execute_sandboxed(
        self,
        *,
        command: str,
        workdir: Path,
        timeout: int,
        security_metadata: dict[str, Any],
        sandbox_config: SandboxConfig,
    ) -> ToolResult:
        sandbox_result = await run_sandboxed(
            command,
            cwd=workdir,
            timeout=timeout,
            config=sandbox_config,
        )
        output = self._truncate(sandbox_result.stdout.decode("utf-8", errors="replace"))
        error_output = self._truncate(sandbox_result.stderr.decode("utf-8", errors="replace"))
        content = "\n".join(
            part
            for part in [
                f"returncode: {sandbox_result.returncode}",
                f"stdout:\n{output}" if output else "stdout:",
                f"stderr:\n{error_output}" if error_output else "stderr:",
            ]
            if part
        )
        metadata = {
            **security_metadata,
            "sandbox": sandbox_result.metadata,
        }
        error = error_output
        if sandbox_result.returncode == 126 and not sandbox_result.fail_open:
            error = "sandbox_unavailable"
        return ToolResult(
            content=content,
            success=sandbox_result.returncode == 0,
            error=error,
            metadata=metadata,
        )

    def _truncate(self, content: str) -> str:
        """把命令输出截断到固定字节上限。"""
        encoded = content.encode("utf-8", errors="replace")
        if len(encoded) <= MAX_OUTPUT_BYTES:
            return content
        return encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace") + "\n[output truncated]"


def _load_sandbox_config() -> SandboxConfig:
    """Load optional bash sandbox configuration from tools.yaml."""
    try:
        tools_config = BambooConfig().get("tools", {})
    except Exception:
        return SandboxConfig()
    if not isinstance(tools_config, dict):
        return SandboxConfig()
    sandbox_config = tools_config.get("sandbox", {})
    return SandboxConfig.from_mapping(sandbox_config if isinstance(sandbox_config, dict) else {})
