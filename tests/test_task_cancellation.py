"""Task cancellation tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient

from bamboo.adapters.web.app import create_app
from bamboo.factory.event_bus import EventBus
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory, LLMResponse, LLMToolCall
from bamboo.runtime.agent_runtime import AgentRuntime
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.runtime.state_machine import AgentState
from bamboo.runtime.store import get_task_store, reset_task_store
from bamboo.runtime.task_runtime import TaskRuntime
from bamboo.security import PermissionDecision, PermissionRequest, PermissionResolver, PermissionResult
from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    reset_task_store()


def test_task_runtime_marks_cancelled_when_worker_is_cancelled(tmp_path: Path) -> None:
    async def run_test() -> None:
        runtime = TaskRuntime(
            llm_factory=LLMFactory.from_mapping(_model_document()),
            agent_factory=lambda event_bus: _SleepingAgent(),
        )
        task = runtime.create_task(RunParams(message="long task", project=str(tmp_path), model="test-model"))
        worker = asyncio.create_task(runtime.run_existing_task(task))
        await asyncio.sleep(0)
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

        snapshot = get_task_store().get(task.task_id)
        assert snapshot is not None
        assert snapshot.status == "cancelled"
        assert snapshot.metadata["stop_reason"] == "cancelled by user"

    anyio.run(run_test)


def test_web_stop_endpoint_marks_known_task_cancelled() -> None:
    app = create_app()
    snapshot = get_task_store().create_task(task_id="task-stop", session_id="session-stop", title="Stop me")
    assert snapshot.status == "created"

    response = TestClient(app).post("/api/tasks/task-stop/stop")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert get_task_store().get("task-stop").status == "cancelled"  # type: ignore[union-attr]


def test_cancel_during_tool_permission_adds_tool_message(tmp_path: Path) -> None:
    async def run_test() -> None:
        event_bus = EventBus()
        registry = ToolRegistry()
        registry.register(_WriteTool(), source="test")
        runtime_context_builder = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=LLMFactory.from_mapping(_model_document()),
            tool_registry=registry,
            permission_resolver=_HangingPermissionResolver(),
        )
        runtime = TaskRuntime(event_bus=event_bus, llm_factory=LLMFactory.from_mapping(_model_document()))
        task = runtime.create_task(RunParams(message="run write", project=str(tmp_path), model="test-model"))
        tool_call = LLMToolCall(id="call-cancel", name="write_tool", arguments={})
        task.session.add_message("assistant", "", tool_calls=[tool_call])
        agent = AgentRuntime(runtime_context=runtime_context_builder.build(task))

        worker = asyncio.create_task(agent._execute_tool_call(task, tool_call))
        await asyncio.sleep(0)
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

        tool_messages = [message for message in task.session.messages if message.role == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0].tool_call_id == "call-cancel"
        assert "Tool call cancelled by user" in tool_messages[0].content

    anyio.run(run_test)


def test_cancel_during_serial_tool_calls_repairs_remaining_tool_messages(tmp_path: Path) -> None:
    async def run_test() -> None:
        event_bus = EventBus()
        registry = ToolRegistry()
        registry.register(_WriteTool(), source="test")
        runtime_context_builder = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=LLMFactory.from_mapping(_model_document()),
            tool_registry=registry,
            permission_resolver=_HangingPermissionResolver(),
        )
        runtime = TaskRuntime(event_bus=event_bus, llm_factory=LLMFactory.from_mapping(_model_document()))
        task = runtime.create_task(RunParams(message="run writes", project=str(tmp_path), model="test-model"))
        tool_calls = [
            LLMToolCall(id="call-cancel-1", name="write_tool", arguments={}),
            LLMToolCall(id="call-cancel-2", name="write_tool", arguments={}),
        ]
        agent = AgentRuntime(runtime_context=runtime_context_builder.build(task))
        agent.state_machine.state = AgentState.ACTING

        worker = asyncio.create_task(
            agent._act(task, LLMResponse(content="", model="test-model", provider="test-provider", tool_calls=tool_calls))
        )
        await asyncio.sleep(0)
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

        tool_messages = [message for message in task.session.messages if message.role == "tool"]
        assert [message.tool_call_id for message in tool_messages] == ["call-cancel-1", "call-cancel-2"]
        assert all("Tool call cancelled by user" in message.content for message in tool_messages)

    anyio.run(run_test)


class _SleepingAgent:
    async def run(self, task):
        await asyncio.sleep(60)
        return task


class _WriteTool(Tool):
    name = "write_tool"
    description = "write tool"
    risk_level = "write"

    async def execute(self, **kwargs):
        return ToolResult(content="done")


class _HangingPermissionResolver(PermissionResolver):
    async def resolve(
        self,
        request: PermissionRequest,
        result: PermissionResult,
        run_params: RunParams,
    ) -> PermissionResult:
        await asyncio.sleep(60)
        return PermissionResult(PermissionDecision.ALLOW, request.risk_level, "approved")


def _model_document() -> dict:
    return {
        "default_model": "test-model",
        "models": {
            "test-model": {
                "provider": "deepseek",
                "model": "provider-model-id",
                "api_key": "test-api-key",
                "base_url": "https://llm.test/v1",
            }
        },
    }
