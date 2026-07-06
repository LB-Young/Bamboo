"""OS sandbox runner tests."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from bamboo.security.sandbox import SandboxConfig, SandboxExecutionResult, build_sandbox_command, run_sandboxed
from bamboo.tools.buildin import bash as bash_module
from bamboo.tools.buildin.bash import BashTool


def test_build_sandbox_command_returns_none_when_runner_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shutil.which", lambda _name: None)

    command = build_sandbox_command("echo hi", cwd=tmp_path, config=SandboxConfig(enabled=True))

    assert command is None


def test_build_sandbox_command_uses_macos_sandbox_exec(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/sandbox-exec" if name == "sandbox-exec" else None)

    command = build_sandbox_command(
        "echo hi",
        cwd=tmp_path,
        config=SandboxConfig(enabled=True, writable_roots=(str(tmp_path),)),
    )

    assert command is not None
    assert command[:3] == ["/usr/bin/sandbox-exec", "-p", command[2]]
    assert command[-3:] == ["/bin/sh", "-lc", "echo hi"]
    assert str(tmp_path) in command[2]


def test_run_sandboxed_fail_closed_when_runner_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("shutil.which", lambda _name: None)

    async def run_test() -> None:
        result = await run_sandboxed(
            "echo hi",
            cwd=tmp_path,
            timeout=1,
            config=SandboxConfig(enabled=True, fail_open=False),
        )
        assert result.returncode == 126
        assert result.sandbox_used is False
        assert result.sandbox_available is False
        assert result.fail_open is False
        assert b"bwrap is not available" in result.stderr

    anyio.run(run_test)


def test_bash_tool_records_sandbox_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_run_sandboxed(command, *, cwd, timeout, config):
        return SandboxExecutionResult(
            returncode=0,
            stdout=b"hello\n",
            stderr=b"",
            sandbox_used=True,
            sandbox_available=True,
            profile="test-sandbox",
            reason="sandboxed",
        )

    monkeypatch.setattr(bash_module, "run_sandboxed", fake_run_sandboxed)

    async def run_test() -> None:
        result = await BashTool(sandbox_config=SandboxConfig(enabled=True)).execute("echo hello", cwd=str(tmp_path))

        assert result.success
        assert "hello" in result.content
        assert result.metadata["sandbox"]["used"] is True  # type: ignore[index]
        assert result.metadata["sandbox"]["profile"] == "test-sandbox"  # type: ignore[index]

    anyio.run(run_test)


def test_bash_tool_fails_when_sandbox_unavailable_and_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_run_sandboxed(command, *, cwd, timeout, config):
        return SandboxExecutionResult(
            returncode=126,
            stdout=b"",
            stderr=b"bwrap is not available",
            sandbox_used=False,
            sandbox_available=False,
            fail_open=False,
            reason="bwrap is not available",
        )

    monkeypatch.setattr(bash_module, "run_sandboxed", fake_run_sandboxed)

    async def run_test() -> None:
        result = await BashTool(sandbox_config=SandboxConfig(enabled=True, fail_open=False))._execute_sandboxed(
            command="echo hello",
            workdir=tmp_path,
            timeout=1,
            security_metadata={"risk": "read", "requires_confirmation": False},
            sandbox_config=SandboxConfig(enabled=True, fail_open=False),
        )

        assert not result.success
        assert result.error == "sandbox_unavailable"
        assert result.metadata["sandbox"]["used"] is False  # type: ignore[index]

    anyio.run(run_test)
