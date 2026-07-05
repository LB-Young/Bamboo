"""Workflow load and run tools."""

from __future__ import annotations

import asyncio
import shlex
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from bamboo.helpers.constant import WorkflowRunCompleteEvent, WorkflowRunStartEvent
from bamboo.security import inspect_command
from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.workflows import WorkflowDefinition, WorkflowRegistry, create_workflow_registry

MAX_OUTPUT_BYTES = 512 * 1024


class WorkflowLoadTool(Tool):
    """Load a workflow entry document before deciding how to run it."""

    name = "workflow_load"
    description = "Load a Bamboo workflow's WORKFLOW.md instructions, dependencies and usage."
    risk_level = "read"
    tags = ("workflow", "read")

    def __init__(self, *, workflow_registry: WorkflowRegistry | None = None) -> None:
        self.workflow_registry = workflow_registry

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Workflow name to load."},
            },
            "required": ["name"],
        }

    async def execute(self, name: str) -> ToolResult:
        registry = self.workflow_registry or create_workflow_registry()
        workflow = registry.get(name)
        if workflow is None:
            available = ", ".join(registry.available_names()) or "none"
            return ToolResult(
                content=f"Workflow not found: {name}\nAvailable workflows: {available}",
                success=False,
                error="workflow_not_found",
                metadata={"available_workflows": registry.available_names()},
            )
        return ToolResult(
            content=_render_workflow_document(workflow),
            metadata={
                "workflow_name": workflow.name,
                "source": workflow.source,
                "source_dir": str(workflow.source_dir),
                "entry_path": str(workflow.entry_path),
            },
        )


class WorkflowRunTool(Tool):
    """Run the command or script declared by a workflow package."""

    name = "workflow_run"
    description = (
        "Run a Bamboo workflow after reading workflow_load output. "
        "Executes the workflow's declared command or script with optional arguments."
    )
    risk_level = "execute"
    tags = ("workflow", "execute")

    def __init__(self, *, workflow_registry: WorkflowRegistry | None = None, default_timeout: int = 120) -> None:
        self.workflow_registry = workflow_registry
        self.default_timeout = default_timeout
        self.runtime_context = None
        self.task = None

    def bind_runtime_context(self, *, runtime_context: object, task: object) -> None:
        self.runtime_context = runtime_context
        self.task = task

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Workflow name to run."},
                "arguments": {"type": "string", "description": "Workflow arguments."},
                "timeout": {"type": "integer", "description": "Optional timeout in seconds."},
            },
            "required": ["name"],
        }

    async def execute(self, name: str, arguments: str = "", timeout: int | None = None) -> ToolResult:
        registry = self.workflow_registry or create_workflow_registry(_task_project(self.task))
        workflow = registry.get(name)
        if workflow is None:
            available = ", ".join(registry.available_names()) or "none"
            return ToolResult(
                content=f"Workflow not found: {name}\nAvailable workflows: {available}",
                success=False,
                error="workflow_not_found",
                metadata={"available_workflows": registry.available_names()},
            )
        try:
            command = _workflow_command(workflow, arguments)
        except ValueError as exc:
            return ToolResult(
                content=f"Workflow `{name}` is invalid: {exc}",
                success=False,
                error="workflow_invalid",
            )
        if not command:
            return ToolResult(
                content=f"Workflow `{name}` does not declare run.command or run.script.",
                success=False,
                error="workflow_not_runnable",
            )
        security = inspect_command(command)
        if not security.allowed:
            return ToolResult(
                content=f"Workflow command blocked: {security.reason}",
                success=False,
                error="command_blocked",
                metadata={"risk": security.risk.value, "requires_confirmation": security.requires_confirmation},
            )

        run_id = str(uuid4())
        started_at = time.perf_counter()
        await _emit_workflow_start(self.runtime_context, self.task, workflow, run_id)
        cwd = _workflow_cwd(workflow)
        exec_timeout = min(timeout or workflow.run.timeout or self.default_timeout, self.default_timeout)
        result = await _run_shell_command(command, cwd=cwd, timeout=exec_timeout)
        duration = time.perf_counter() - started_at
        status = "completed" if result["returncode"] == 0 else "failed"
        await _emit_workflow_complete(self.runtime_context, self.task, workflow, run_id, status, duration)
        metadata = {
            "workflow_name": workflow.name,
            "run_id": run_id,
            "command": command,
            "cwd": str(cwd),
            "declared_risk": workflow.run.risk,
            "risk": security.risk.value,
            "requires_confirmation": security.requires_confirmation,
        }
        return ToolResult(
            content=result["content"],
            success=result["returncode"] == 0,
            error=result["stderr"],
            metadata=metadata,
        )


def _render_workflow_document(workflow: WorkflowDefinition) -> str:
    sections = [
        f"# Workflow: {workflow.name}",
        f"Description: {workflow.description or '(none)'}",
        f"Source: {workflow.source}",
        f"Entry: {workflow.entry_path}",
    ]
    if workflow.usage:
        sections.append(f"Usage:\n{workflow.usage}")
    if workflow.dependencies:
        sections.append("Dependencies:\n" + "\n".join(f"- {item}" for item in workflow.dependencies))
    if workflow.run.command:
        sections.append(f"Run command:\n```bash\n{workflow.run.command}\n```")
    if workflow.run.script:
        sections.append(f"Run script: `{workflow.run.script}`")
    sections.append(f"Declared risk: {workflow.run.risk}")
    if workflow.body:
        sections.append(workflow.body)
    return "\n\n".join(sections)


def _workflow_command(workflow: WorkflowDefinition, arguments: str) -> str:
    if workflow.run.command:
        return _render_text(workflow.run.command, arguments)
    if workflow.run.script:
        script_path = (workflow.source_dir / workflow.run.script).resolve()
        source_dir = workflow.source_dir.resolve()
        if source_dir not in script_path.parents and script_path != source_dir:
            raise ValueError("workflow script must stay inside workflow directory")
        if not script_path.is_file():
            raise ValueError(f"workflow script not found: {workflow.run.script}")
        command = f"bash {shlex.quote(str(script_path))}"
        if arguments.strip():
            command = f"{command} {shlex.quote(arguments.strip())}"
        return command
    return ""


def _workflow_cwd(workflow: WorkflowDefinition) -> Path:
    cwd = Path(workflow.run.cwd)
    if not cwd.is_absolute():
        cwd = workflow.source_dir / cwd
    return cwd.expanduser().resolve()


def _render_text(text: str, arguments: str) -> str:
    return text.replace("$ARGUMENTS", arguments.strip()).replace("{{arguments}}", arguments.strip())


async def _run_shell_command(command: str, *, cwd: Path, timeout: int) -> dict[str, Any]:
    if not cwd.exists() or not cwd.is_dir():
        return {"returncode": 1, "stdout": "", "stderr": f"Invalid cwd: {cwd}", "content": f"Invalid cwd: {cwd}"}
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return {
            "returncode": 124,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "content": f"Command timed out after {timeout}s",
        }
    stdout_text = _truncate(stdout.decode("utf-8", errors="replace"))
    stderr_text = _truncate(stderr.decode("utf-8", errors="replace"))
    content = "\n".join(
        [
            f"returncode: {process.returncode}",
            f"stdout:\n{stdout_text}" if stdout_text else "stdout:",
            f"stderr:\n{stderr_text}" if stderr_text else "stderr:",
        ]
    )
    return {"returncode": process.returncode, "stdout": stdout_text, "stderr": stderr_text, "content": content}


def _truncate(content: str) -> str:
    encoded = content.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return content
    return encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace") + "\n[output truncated]"


def _task_project(task: object | None) -> str | Path | None:
    run_params = getattr(task, "run_params", None)
    return getattr(run_params, "project", None)


async def _emit_workflow_start(runtime_context: object | None, task: object | None, workflow: WorkflowDefinition, run_id: str) -> None:
    event_bus = getattr(runtime_context, "event_bus", None)
    if event_bus is None or task is None:
        return
    await event_bus.emit(
        WorkflowRunStartEvent(
            session_id=getattr(task, "session_id", ""),
            task_id=getattr(task, "task_id", ""),
            run_id=run_id,
            workflow_id=workflow.name,
        )
    )


async def _emit_workflow_complete(
    runtime_context: object | None,
    task: object | None,
    workflow: WorkflowDefinition,
    run_id: str,
    status: str,
    duration: float,
) -> None:
    event_bus = getattr(runtime_context, "event_bus", None)
    if event_bus is None or task is None:
        return
    await event_bus.emit(
        WorkflowRunCompleteEvent(
            session_id=getattr(task, "session_id", ""),
            task_id=getattr(task, "task_id", ""),
            run_id=run_id,
            workflow_id=workflow.name,
            status=status,
            duration_seconds=duration,
        )
    )
