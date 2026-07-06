"""OS sandbox runner for shell commands."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_ENV_ALLOWLIST = ("PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR")


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    """Describes execution limits for a future sandbox runner."""

    enabled: bool = False
    writable_roots: tuple[str, ...] = ()
    env_allowlist: tuple[str, ...] = DEFAULT_ENV_ALLOWLIST
    network_enabled: bool = False
    fail_open: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "SandboxConfig":
        """Create config from tools.yaml sandbox mapping."""
        if not isinstance(value, dict):
            return cls()
        writable_roots = value.get("writable_roots", ())
        env_allowlist = value.get("env_allowlist", DEFAULT_ENV_ALLOWLIST)
        metadata = value.get("metadata", {})
        return cls(
            enabled=bool(value.get("enabled", False)),
            writable_roots=tuple(str(item) for item in writable_roots) if isinstance(writable_roots, list) else (),
            env_allowlist=tuple(str(item) for item in env_allowlist) if isinstance(env_allowlist, list) else DEFAULT_ENV_ALLOWLIST,
            network_enabled=bool(value.get("network_enabled", False)),
            fail_open=bool(value.get("fail_open", False)),
            metadata={str(key): str(item) for key, item in metadata.items()} if isinstance(metadata, dict) else {},
        )


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Result returned by sandbox policy checks."""

    allowed: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class SandboxExecutionResult:
    """Result of running a command through sandbox policy."""

    returncode: int
    stdout: bytes = b""
    stderr: bytes = b""
    sandbox_used: bool = False
    sandbox_available: bool = False
    profile: str = ""
    fail_open: bool = False
    reason: str = ""

    @property
    def metadata(self) -> dict[str, Any]:
        """Return JSON-serializable sandbox metadata."""
        return {
            "enabled": True,
            "used": self.sandbox_used,
            "available": self.sandbox_available,
            "profile": self.profile,
            "fail_open": self.fail_open,
            "reason": self.reason,
        }


async def run_sandboxed(
    command: str,
    *,
    cwd: Path,
    timeout: int,
    config: SandboxConfig,
) -> SandboxExecutionResult:
    """Run a shell command through the configured OS sandbox."""
    sandbox_command = build_sandbox_command(command, cwd=cwd, config=config)
    env = _sandbox_env(config)
    if sandbox_command is None:
        reason = _unavailable_reason()
        if not config.fail_open:
            return SandboxExecutionResult(
                returncode=126,
                stderr=reason.encode("utf-8"),
                sandbox_available=False,
                fail_open=False,
                reason=reason,
            )
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await _communicate(process, timeout=timeout)
        return SandboxExecutionResult(
            returncode=process.returncode if process.returncode is not None else 1,
            stdout=stdout,
            stderr=stderr,
            sandbox_used=False,
            sandbox_available=False,
            fail_open=True,
            reason=reason,
        )

    process = await asyncio.create_subprocess_exec(
        *sandbox_command,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await _communicate(process, timeout=timeout)
    return SandboxExecutionResult(
        returncode=process.returncode if process.returncode is not None else 1,
        stdout=stdout,
        stderr=stderr,
        sandbox_used=True,
        sandbox_available=True,
        profile=_sandbox_profile_name(),
        fail_open=False,
        reason="sandboxed",
    )


def build_sandbox_command(command: str, *, cwd: Path, config: SandboxConfig) -> list[str] | None:
    """Build the platform sandbox command, or None when unavailable."""
    system = platform.system()
    if system == "Darwin":
        sandbox_exec = shutil.which("sandbox-exec")
        if sandbox_exec is None:
            return None
        return [sandbox_exec, "-p", _macos_sandbox_profile(config), "/bin/sh", "-lc", command]
    if system == "Linux":
        bwrap = shutil.which("bwrap")
        if bwrap is None:
            return None
        args = [
            bwrap,
            "--die-with-parent",
            "--ro-bind",
            "/",
            "/",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--tmpfs",
            "/tmp",
            "--chdir",
            str(cwd),
        ]
        if not config.network_enabled:
            args.append("--unshare-net")
        for root in config.writable_roots:
            path = str(Path(root).expanduser().resolve(strict=False))
            args.extend(["--bind", path, path])
        args.extend(["/bin/sh", "-lc", command])
        return args
    return None


async def _communicate(process: asyncio.subprocess.Process, *, timeout: int) -> tuple[bytes, bytes]:
    try:
        return await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return b"", f"Command timed out after {timeout}s".encode("utf-8")


def _sandbox_env(config: SandboxConfig) -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key in set(config.env_allowlist)}


def _macos_sandbox_profile(config: SandboxConfig) -> str:
    network_rule = "(allow network*)" if config.network_enabled else "(deny network*)"
    write_rules = "\n".join(
        f'(allow file-write* (subpath "{Path(root).expanduser().resolve(strict=False)}"))'
        for root in config.writable_roots
    )
    return "\n".join(
        [
            "(version 1)",
            "(deny default)",
            "(allow process*)",
            "(allow file-read*)",
            '(allow file-write* (subpath "/tmp"))',
            '(allow file-write* (subpath "/private/tmp"))',
            write_rules,
            network_rule,
        ]
    )


def _sandbox_profile_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return "sandbox-exec"
    if system == "Linux":
        return "bwrap"
    return "unsupported"


def _unavailable_reason() -> str:
    system = platform.system()
    if system == "Darwin":
        return "sandbox-exec is not available"
    if system == "Linux":
        return "bwrap is not available"
    return f"OS sandbox is not supported on {system}"
