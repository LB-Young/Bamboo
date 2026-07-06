"""Bamboo CLI 适配层。

该模块负责把命令行会话接入运行时：先订阅 EventBus，再启动
TaskRuntime，最后把运行时事件渲染到终端。
"""

from __future__ import annotations

import anyio
import json
from pathlib import Path
from rich.console import Console

from bamboo.factory.event_bus import EventBus, get_event_bus
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import (
    PermissionRequestEvent,
    PermissionResultEvent,
    SessionStatusChangeEvent,
    StepFinishEvent,
    StepStartEvent,
    SubagentFinishEvent,
    SubagentStartEvent,
    TaskCreateEvent,
    TaskStatusChangeEvent,
    TextDeltaEvent,
    TextFinishEvent,
    TextStartEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
    CronJobCompleteEvent,
    CronJobStartEvent,
)
from bamboo.helpers.logging import get_logger
from bamboo.helpers.requests_params import RunParams
from bamboo.helpers.utils import BaseEvent
from bamboo.runtime import TaskRuntime
from bamboo.adapters.cli.commands import expand_command_message
from bamboo.memory.session_store import find_session_record, load_session_record

console = Console()

CLI_EVENT_PATTERNS = {
    "task.*",
    "session.*",
    "step.*",
    "text.*",
    "permission.*",
    "subagent.*",
    "tool.*",
    "cron.*",
}


async def _start_session(run_params: RunParams) -> object:
    """启动一个 CLI 任务会话，并渲染当前 session 的事件流。"""
    log = get_logger("cli")
    expanded = expand_command_message(run_params.message, project=run_params.project)
    if expanded.error:
        console.print(f"[red]command error[/red] {expanded.error}")
        raise ValueError(expanded.error)
    if expanded.expanded:
        console.print(f"[dim]command expanded[/dim] /{expanded.command_name}")
        run_params.message = expanded.message
    event_bus = get_event_bus()
    # 先订阅事件，再启动任务，确保 task-created 等早期事件不会丢失。
    unsubscribe = event_bus.subscribe(
        _render_cli_event,
        patterns=CLI_EVENT_PATTERNS,
        filter_fn=lambda event: event.session_id == run_params.session_id,
    )
    debug_unsubscribe = _subscribe_debug_events(event_bus, run_params)

    try:
        # CLI 层不直接运行 Agent，只把控制权交给 TaskRuntime。
        runtime = TaskRuntime(event_bus=event_bus)
        task = runtime.create_task(run_params)
        task = await runtime.run_existing_task(task)
        log.debug(
            "task completed task_id={task_id} session_id={session_id}",
            task_id=task.task_id,
            session_id=task.session_id,
        )
        return task
    finally:
        # 会话结束后解除订阅，避免后续任务重复渲染旧 handler。
        unsubscribe()
        debug_unsubscribe()


async def _start_resumed_session(run_params: RunParams, *, record_dir: str | None = None) -> object:
    """恢复一个已持久化 session，并把当前 message 作为 follow-up task 执行。"""
    if not run_params.session_id:
        raise ValueError("--resume requires a session id")
    if not run_params.message.strip():
        raise ValueError("resumed non-interactive session requires a message")
    runtime = TaskRuntime(event_bus=get_event_bus())
    task = _create_resumed_followup_task(runtime, run_params, record_dir=record_dir)
    run_params.session_id = task.session_id

    event_bus = get_event_bus()
    unsubscribe = event_bus.subscribe(
        _render_cli_event,
        patterns=CLI_EVENT_PATTERNS,
        filter_fn=lambda event: event.session_id == task.session_id,
    )
    debug_unsubscribe = _subscribe_debug_events(event_bus, run_params)
    try:
        task = await runtime.run_existing_task(task)
        return task
    finally:
        unsubscribe()
        debug_unsubscribe()


async def _start_interactive_session(run_params: RunParams) -> object:
    """启动交互式 CLI 会话，并在多轮输入之间复用同一个 Session。"""
    log = get_logger("cli")
    event_bus = get_event_bus()
    unsubscribe = event_bus.subscribe(
        _render_cli_event,
        patterns=CLI_EVENT_PATTERNS,
        filter_fn=lambda event: event.session_id == run_params.session_id,
    )
    debug_unsubscribe = _subscribe_debug_events(event_bus, run_params)

    runtime = TaskRuntime(event_bus=event_bus)
    task = runtime.create_task(run_params)
    console.print(
        "[green]Bamboo interactive session started[/green] "
        f"[dim]session_id={task.session_id} mode={run_params.session_mode_value}[/dim]"
    )
    console.print("[dim]输入 /exit 或 /quit 结束会话。[/dim]")

    try:
        while True:
            user_input = await anyio.to_thread.run_sync(lambda: console.input("[bold cyan]you> [/bold cyan]"))
            message = user_input.strip()
            if not message:
                continue
            if message in {"/exit", "/quit", "exit", "quit"}:
                console.print("[green]bye[/green]")
                return task
            expanded = expand_command_message(message, project=run_params.project)
            if expanded.error:
                console.print(f"[red]command error[/red] {expanded.error}")
                if expanded.available_commands:
                    console.print(f"[dim]available[/dim] {', '.join(expanded.available_commands)}")
                continue
            if expanded.expanded:
                console.print(f"[dim]command expanded[/dim] /{expanded.command_name}")
                message = expanded.message

            previous_task = task
            message_checkpoint = len(previous_task.session.messages)
            task = runtime.create_followup_task(previous_task, message)
            failed_task_id = task.task_id
            try:
                task = await runtime.run_existing_task(task)
            except Exception as exc:
                del previous_task.session.messages[message_checkpoint:]
                task = previous_task
                log.exception(
                    "interactive turn failed task_id={task_id} session_id={session_id}",
                    task_id=failed_task_id,
                    session_id=previous_task.session_id,
                )
                console.print(f"[red]task failed[/red] {exc}")
                continue
            log.debug(
                "interactive turn completed task_id={task_id} session_id={session_id}",
                task_id=task.task_id,
                session_id=task.session_id,
            )
    finally:
        unsubscribe()
        debug_unsubscribe()


async def _start_resumed_interactive_session(run_params: RunParams, *, record_dir: str | None = None) -> object:
    """恢复一个已持久化 session，并进入交互式 follow-up 循环。"""
    if not run_params.session_id:
        raise ValueError("--resume requires a session id")
    log = get_logger("cli")
    event_bus = get_event_bus()
    runtime = TaskRuntime(event_bus=event_bus)
    task = _restore_previous_task(runtime, run_params, record_dir=record_dir)
    run_params.session_id = task.session_id
    unsubscribe = event_bus.subscribe(
        _render_cli_event,
        patterns=CLI_EVENT_PATTERNS,
        filter_fn=lambda event: event.session_id == task.session_id,
    )
    debug_unsubscribe = _subscribe_debug_events(event_bus, run_params)

    console.print(
        "[green]Bamboo interactive session resumed[/green] "
        f"[dim]session_id={task.session_id} mode={run_params.session_mode_value}[/dim]"
    )
    console.print("[dim]输入 /exit 或 /quit 结束会话。[/dim]")
    try:
        while True:
            user_input = await anyio.to_thread.run_sync(lambda: console.input("[bold cyan]you> [/bold cyan]"))
            message = user_input.strip()
            if not message:
                continue
            if message in {"/exit", "/quit", "exit", "quit"}:
                console.print("[green]bye[/green]")
                return task
            expanded = expand_command_message(message, project=run_params.project)
            if expanded.error:
                console.print(f"[red]command error[/red] {expanded.error}")
                if expanded.available_commands:
                    console.print(f"[dim]available[/dim] {', '.join(expanded.available_commands)}")
                continue
            if expanded.expanded:
                console.print(f"[dim]command expanded[/dim] /{expanded.command_name}")
                message = expanded.message

            previous_task = task
            message_checkpoint = len(previous_task.session.messages)
            task = runtime.create_followup_task(previous_task, message)
            failed_task_id = task.task_id
            try:
                task = await runtime.run_existing_task(task)
            except Exception as exc:
                del previous_task.session.messages[message_checkpoint:]
                task = previous_task
                log.exception(
                    "resumed interactive turn failed task_id={task_id} session_id={session_id}",
                    task_id=failed_task_id,
                    session_id=previous_task.session_id,
                )
                console.print(f"[red]task failed[/red] {exc}")
                continue
    finally:
        unsubscribe()
        debug_unsubscribe()


def _create_resumed_followup_task(runtime: TaskRuntime, run_params: RunParams, *, record_dir: str | None) -> Task:
    """Restore previous session and create one follow-up task."""
    previous = _restore_previous_task(runtime, run_params, record_dir=record_dir)
    expanded = expand_command_message(run_params.message, project=run_params.project)
    if expanded.error:
        console.print(f"[red]command error[/red] {expanded.error}")
        raise ValueError(expanded.error)
    message = expanded.message if expanded.expanded else run_params.message
    if expanded.expanded:
        console.print(f"[dim]command expanded[/dim] /{expanded.command_name}")
    return runtime.create_followup_task(previous, message)


def _restore_previous_task(runtime: TaskRuntime, run_params: RunParams, *, record_dir: str | None) -> Task:
    """Create a Task wrapper around a persisted Session without appending a new message."""
    resolved = find_session_record(
        run_params.session_id,
        mode=run_params.session_mode_value,
        project_path=Path(run_params.project) if run_params.session_mode_value == "project" else None,
        record_dir=record_dir,
    )
    if resolved is None:
        raise ValueError(f"Session not found: {run_params.session_id}")
    session = load_session_record(resolved)
    session.current_task_id = run_params.task_id
    run_params.session_id = session.session_id
    run_params.project = str(session.context.project_root)
    run_params.model = run_params.model or session.model
    run_params.provider = run_params.provider or session.provider
    return Task(
        platform=run_params.platform,
        session_id=session.session_id,
        task_id=run_params.task_id,
        user_query="",
        session=session,
        config=runtime.task_factory.config,
        run_params=run_params,
        memory_dir=session.memory_store.memory_dir if session.memory_store else resolved.parent,
    )


def _subscribe_debug_events(event_bus: EventBus, run_params: RunParams):
    """按需订阅并打印当前 session 的完整脱敏事件。"""
    if not run_params.debug_events:
        return lambda: None
    return event_bus.subscribe(
        _render_debug_event,
        patterns="*",
        filter_fn=lambda event: event.session_id == run_params.session_id,
    )


def _render_debug_event(event: BaseEvent) -> None:
    """输出原始事件 JSON，供 CLI 调试 trace 使用。"""
    console.print(f"[dim][event][/dim] {json.dumps(event.to_dict(), ensure_ascii=False)}")


def _render_cli_event(event: BaseEvent) -> None:
    """把一条运行时事件渲染为终端输出。"""
    if isinstance(event, TaskCreateEvent):
        console.print(f"[dim]task created[/dim] {event.task_id} {event.title}")
        return

    if isinstance(event, TaskStatusChangeEvent):
        console.print(f"[dim]task status[/dim] {event.from_status or '-'} -> {event.to_status}")
        return

    if isinstance(event, SessionStatusChangeEvent):
        console.print(f"[dim]agent state[/dim] {event.status} [dim]{event.reason}[/dim]")
        return

    if isinstance(event, StepStartEvent):
        console.print(f"[dim]step start[/dim] {event.step_id}")
        return

    if isinstance(event, TextStartEvent):
        console.print("[dim]assistant[/dim]")
        return

    if isinstance(event, TextDeltaEvent):
        console.print(event.delta)
        return

    if isinstance(event, TextFinishEvent):
        return

    if isinstance(event, ToolCallEvent):
        console.print(f"[dim]tool call[/dim] {event.tool_name} {event.tool_input}")
        return

    if isinstance(event, PermissionRequestEvent):
        console.print(
            f"[yellow]permission required[/yellow] {event.tool_name} "
            f"[dim]risk={event.risk_level} reason={event.reason}[/dim]"
        )
        return

    if isinstance(event, PermissionResultEvent):
        status = "approved" if event.approved else "denied"
        console.print(f"[dim]permission {status}[/dim] {event.tool_name} {event.reason}")
        return

    if isinstance(event, SubagentStartEvent):
        console.print(f"[dim]subagent start[/dim] {event.subagent_name} {event.description}")
        return

    if isinstance(event, SubagentFinishEvent):
        console.print(f"[dim]subagent finish[/dim] {event.subagent_name} status={event.status}")
        return

    if isinstance(event, ToolResultEvent):
        console.print(f"[dim]tool result[/dim] {event.tool_name}\n{event.output}")
        return

    if isinstance(event, ToolErrorEvent):
        console.print(f"[red]tool error[/red] {event.tool_name}: {event.error}")
        return

    if isinstance(event, StepFinishEvent):
        console.print(f"[dim]step finish[/dim] {event.summary}")
        return

    if isinstance(event, CronJobStartEvent):
        console.print(f"[dim]cron start[/dim] {event.job_name} delivery={event.delivery}")
        return

    if isinstance(event, CronJobCompleteEvent):
        color = "green" if event.status == "completed" else "red"
        console.print(f"[{color}]cron {event.status}[/{color}] {event.job_name} {event.error}")
