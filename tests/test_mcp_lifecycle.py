"""MCP lifecycle cleanup tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import anyio
import pytest

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import AuditEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.runtime.task_runtime import TaskRecoveryPolicy, TaskRuntime
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.tools import ToolRegistry
from bamboo.tools.mcp import MCPManager


def test_mcp_manager_stop_all_is_idempotent_and_records_stop_errors() -> None:
    manager = MCPManager([])
    manager.clients["broken"] = _BrokenClient()

    manager.stop_all()
    manager.stop_all()

    assert manager.clients == {}
    assert manager.stopped is True
    assert manager.stop_errors == {"broken": "stop failed"}
    assert manager.has_errors is True


def test_runtime_context_builder_close_stops_owned_mcp_manager(tmp_path: Path) -> None:
    server = _write_fake_mcp_server(tmp_path)
    config = _ConfigWithMCP(server)
    task = TaskFactory(config=config).create(RunParams(message="hello", model="test-model"))
    llm_factory = LLMFactory.from_mapping(config.get("models"))
    event_bus = EventBus()
    events: list[object] = []
    event_bus.subscribe(events.append)
    builder = RuntimeContextBuilder(
        event_bus=event_bus,
        llm_factory=llm_factory,
        tool_registry=ToolRegistry(),
    )

    async def run_test() -> None:
        context = builder.build(task)
        manager = context.mcp_manager
        assert manager is not None
        assert manager.clients
        assert context.mcp_manager_owned is True

        await builder.close(task)

        assert manager.clients == {}
        assert manager.stopped is True
        assert builder.mcp_manager is None
        assert any(isinstance(event, AuditEvent) and event.action == "mcp_runtime_builder_closed" for event in events)

    anyio.run(run_test)


def test_task_runtime_calls_context_cleanup_on_success(tmp_path: Path) -> None:
    builder = _CloseTrackingBuilder()
    runtime = TaskRuntime(
        llm_factory=LLMFactory.from_mapping(_model_document()),
        runtime_context_builder=builder,
        agent_factory=lambda _event_bus: _SuccessfulAgent(),
    )
    task = TaskFactory().create(RunParams(message="hello", model="test-model"))

    async def run_test() -> None:
        result = await runtime.run_existing_task(task)
        assert result.output == "done"

    anyio.run(run_test)

    assert builder.closed_task_ids == [task.task_id]


def test_task_runtime_calls_context_cleanup_on_failure(tmp_path: Path) -> None:
    builder = _CloseTrackingBuilder()
    runtime = TaskRuntime(
        llm_factory=LLMFactory.from_mapping(_model_document()),
        runtime_context_builder=builder,
        recovery_policy=TaskRecoveryPolicy(max_agent_attempts=1, continue_after_agent_error=False),
        agent_factory=lambda _event_bus: _FailingAgent(),
    )
    task = TaskFactory().create(RunParams(message="hello", model="test-model"))

    async def run_test() -> None:
        with pytest.raises(RuntimeError, match="agent boom"):
            await runtime.run_existing_task(task)

    anyio.run(run_test)

    assert builder.closed_task_ids == [task.task_id]


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


def _write_fake_mcp_server(tmp_path: Path) -> Path:
    server = tmp_path / "fake_mcp_server.py"
    server.write_text(
        """
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if "id" not in request:
        continue
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {}}
    elif method == "tools/list":
        result = {"tools": []}
    else:
        result = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}) + "\\n")
    sys.stdout.flush()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return server


class _ConfigWithMCP:
    def __init__(self, server: Path) -> None:
        self.server = server

    def get(self, name: str, default: object = None) -> object:
        if name == "models":
            return _model_document()
        if name == "mcp":
            return {
                "mcp": {
                    "auto_start": True,
                    "servers": {
                        "time": {
                            "command": sys.executable,
                            "args": [str(self.server)],
                        }
                    },
                }
            }
        return default


class _BrokenClient:
    def stop(self) -> None:
        raise RuntimeError("stop failed")


class _CloseTrackingBuilder:
    def __init__(self) -> None:
        self.closed_task_ids: list[str] = []

    async def close(self, task) -> None:
        self.closed_task_ids.append(task.task_id)


class _SuccessfulAgent:
    async def run(self, task):
        task.output = "done"
        return task


class _FailingAgent:
    async def run(self, task):
        raise RuntimeError("agent boom")
