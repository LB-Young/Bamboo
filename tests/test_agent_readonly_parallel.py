"""AgentRuntime read-only tool parallelism tests."""

from __future__ import annotations

from typing import Any

import anyio

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import PermissionResultEvent, ToolAuditEvent, ToolResultEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMClient, LLMFactory, LLMRequest, LLMResponse, LLMToolCall
from bamboo.runtime.agent_runtime import AgentRuntime
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.security import ToolAuditLogger
from bamboo.tools.buildin.base import ToolResult
from bamboo.tools.registry import ToolRegistry


def test_agent_runtime_parallelizes_same_turn_read_tools(tmp_path) -> None:
    state: dict[str, Any] = {"active": 0, "max_active": 0}
    registry = ToolRegistry()
    registry.register(_SleepingTool("read_a", risk_level="read", state=state), source="test")
    registry.register(_SleepingTool("read_b", risk_level="read", state=state), source="test")
    events: list[object] = []
    task = TaskFactory().create(RunParams(message="read both", model="test-model"))
    llm_client = _ToolsThenDoneLLMClient(
        [
            LLMToolCall(id="call-read-a", name="read_a", arguments={"value": "A"}),
            LLMToolCall(id="call-read-b", name="read_b", arguments={"value": "B"}),
        ]
    )

    async def run_test() -> None:
        runtime = _build_runtime(
            task=task,
            registry=registry,
            events=events,
            llm_client=llm_client,
            audit_path=tmp_path / "audit.jsonl",
        )
        completed = await runtime.run(task)
        assert completed.output == "done"

    anyio.run(run_test)

    assert state["max_active"] == 2
    assert [
        message.tool_call_id
        for message in task.session.messages
        if message.role == "tool"
    ] == ["call-read-a", "call-read-b"]
    assert sum(isinstance(event, PermissionResultEvent) for event in events) == 2
    assert sum(isinstance(event, ToolAuditEvent) for event in events) == 2
    assert sum(isinstance(event, ToolResultEvent) for event in events) == 2


def test_agent_runtime_keeps_mixed_risk_tool_calls_sequential(tmp_path) -> None:
    state: dict[str, Any] = {"active": 0, "max_active": 0}
    registry = ToolRegistry()
    registry.register(_SleepingTool("read_a", risk_level="read", state=state), source="test")
    registry.register(_SleepingTool("write_a", risk_level="write", state=state), source="test")
    task = TaskFactory().create(RunParams(message="read and write", model="test-model", yes_all=True))
    llm_client = _ToolsThenDoneLLMClient(
        [
            LLMToolCall(id="call-read-a", name="read_a", arguments={"value": "A"}),
            LLMToolCall(id="call-write-a", name="write_a", arguments={"value": "W"}),
        ]
    )

    async def run_test() -> None:
        runtime = _build_runtime(
            task=task,
            registry=registry,
            events=[],
            llm_client=llm_client,
            audit_path=tmp_path / "audit.jsonl",
        )
        completed = await runtime.run(task)
        assert completed.output == "done"

    anyio.run(run_test)

    assert state["max_active"] == 1
    assert [
        message.tool_call_id
        for message in task.session.messages
        if message.role == "tool"
    ] == ["call-read-a", "call-write-a"]


def _build_runtime(
    *,
    task,
    registry: ToolRegistry,
    events: list[object],
    llm_client: LLMClient,
    audit_path,
) -> AgentRuntime:
    factory = LLMFactory.from_mapping(_model_document())
    factory.register_provider("deepseek", lambda config: llm_client, replace=True)
    event_bus = EventBus()
    event_bus.subscribe(events.append)
    runtime_context = RuntimeContextBuilder(
        event_bus=event_bus,
        llm_factory=factory,
        tool_registry=registry,
        audit_logger=ToolAuditLogger(audit_path),
    ).build(task)
    return AgentRuntime(runtime_context=runtime_context)


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


class _SleepingTool:
    description = "Sleep briefly and return a value."
    tags = ("test",)

    def __init__(self, name: str, *, risk_level: str, state: dict[str, Any]) -> None:
        self.name = name
        self.risk_level = risk_level
        self.state = state

    def input_schema(self) -> dict:
        return {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema()}

    async def execute(self, value: str) -> ToolResult:
        self.state["active"] += 1
        self.state["max_active"] = max(self.state["max_active"], self.state["active"])
        await anyio.sleep(0.05)
        self.state["active"] -= 1
        return ToolResult(content=f"{self.name}:{value}", success=True)


class _ToolsThenDoneLLMClient(LLMClient):
    def __init__(self, tool_calls: list[LLMToolCall]) -> None:
        self.tool_calls = tool_calls
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            return LLMResponse(
                content="",
                model="provider-model-id",
                provider="deepseek",
                finish_reason="tool_calls",
                tool_calls=list(self.tool_calls),
            )
        return LLMResponse(
            content="done",
            model="provider-model-id",
            provider="deepseek",
            finish_reason="stop",
        )
