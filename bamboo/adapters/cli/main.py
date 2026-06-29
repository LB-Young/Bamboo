"""Bamboo CLI 适配层。

该模块负责把命令行会话接入运行时：先订阅 EventBus，再启动
TaskRuntime，最后把运行时事件渲染到终端。
"""

from __future__ import annotations

import anyio
from rich.console import Console

from bamboo.factory.event_bus import get_event_bus
from bamboo.helpers.constant import (
    SessionStatusChangeEvent,
    StepFinishEvent,
    StepStartEvent,
    TaskCreateEvent,
    TaskStatusChangeEvent,
    TextDeltaEvent,
    TextFinishEvent,
    TextStartEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
)
from bamboo.helpers.logging import get_logger
from bamboo.helpers.requests_params import RunParams
from bamboo.helpers.utils import BaseEvent
from bamboo.runtime import TaskRuntime

console = Console()


async def _start_session(run_params: RunParams) -> object:
    """启动一个 CLI 任务会话，并渲染当前 session 的事件流。"""
    log = get_logger("cli")
    event_bus = get_event_bus()
    # 先订阅事件，再启动任务，确保 task-created 等早期事件不会丢失。
    unsubscribe = event_bus.subscribe(
        _render_cli_event,
        event_types={
            "task-create",
            "task-status-change",
            "session-status-change",
            "step-start",
            "step-finish",
            "text-start",
            "text-delta",
            "text-finish",
            "tool-call",
            "tool-result",
            "tool-error",
        },
        filter_fn=lambda event: event.session_id == run_params.session_id,
    )

    try:
        # CLI 层不直接运行 Agent，只把控制权交给 TaskRuntime。
        runtime = TaskRuntime(event_bus=event_bus)
        task = runtime.create_task(run_params)
        task = await runtime.run_existing_task(task)
        log.info(
            "task completed task_id={task_id} session_id={session_id}",
            task_id=task.task_id,
            session_id=task.session_id,
        )
        return task
    finally:
        # 会话结束后解除订阅，避免后续任务重复渲染旧 handler。
        unsubscribe()


async def _start_interactive_session(run_params: RunParams) -> object:
    """启动交互式 CLI 会话，并在多轮输入之间复用同一个 Session。"""
    log = get_logger("cli")
    event_bus = get_event_bus()
    unsubscribe = event_bus.subscribe(
        _render_cli_event,
        event_types={
            "task-create",
            "task-status-change",
            "session-status-change",
            "step-start",
            "step-finish",
            "text-start",
            "text-delta",
            "text-finish",
            "tool-call",
            "tool-result",
            "tool-error",
        },
        filter_fn=lambda event: event.session_id == run_params.session_id,
    )

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
            log.info(
                "interactive turn completed task_id={task_id} session_id={session_id}",
                task_id=task.task_id,
                session_id=task.session_id,
            )
    finally:
        unsubscribe()


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

    if isinstance(event, ToolResultEvent):
        console.print(f"[dim]tool result[/dim] {event.tool_name}\n{event.output}")
        return

    if isinstance(event, ToolErrorEvent):
        console.print(f"[red]tool error[/red] {event.tool_name}: {event.error}")
        return

    if isinstance(event, StepFinishEvent):
        console.print(f"[dim]step finish[/dim] {event.summary}")
