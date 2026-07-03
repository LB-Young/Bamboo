"""Tests for tool result context budgeting."""

from __future__ import annotations

from pathlib import Path

import anyio

from bamboo.factory.event_bus import EventBus
from bamboo.factory.session import Session
from bamboo.factory.context import Context
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import ToolResultEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMClient, LLMFactory, LLMRequest, LLMResponse, LLMToolCall
from bamboo.runtime.agent_runtime import AgentRuntime
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.runtime.tool_result_budget import ToolResultBudgetPolicy, ToolResultBudgeter
from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.registry import ToolRegistry


def _model_document() -> dict:
    return {
        "default_model": "tool-model",
        "models": {
            "tool-model": {
                "provider": "deepseek",
                "model": "provider-model-id",
                "api_key": "test-api-key",
                "base_url": "https://llm.test/v1",
                "max_tokens": 128,
                "temperature": 0.1,
            }
        },
    }


def test_budgeter_truncates_single_large_result() -> None:
    budgeter = ToolResultBudgeter(
        policy=ToolResultBudgetPolicy(
            max_single_result_tokens=20,
            preserve_head_chars=16,
            preserve_tail_chars=12,
        )
    )
    result = budgeter.prepare_for_session("A" * 1000 + "THE_END")

    assert result.truncated is True
    assert result.original_length == 1007
    assert result.context_length < result.original_length
    assert "tool output exceeded context budget" in result.context_content
    assert result.context_content.endswith("THE_END")


def test_budgeter_compacts_old_tool_results_when_total_budget_exceeded() -> None:
    session = Session(
        session_id="session-1",
        model="tool-model",
        provider="deepseek",
        context=Context(
            session_id="session-1",
            project_root=Path.cwd(),
            memory_dir=Path.cwd(),
            system_prompt="system",
        ),
    )
    session.add_message("user", "hello")
    first = session.add_message("tool", "A" * 2000, tool_name="first", tool_call_id="call-1")
    second = session.add_message("tool", "B" * 2000, tool_name="second", tool_call_id="call-2")

    budgeter = ToolResultBudgeter(policy=ToolResultBudgetPolicy(max_total_result_tokens=200))
    budgeter.compact_old_tool_results(session)

    assert first.metadata["tool_result_budget_compacted"] is True
    assert "older tool output exceeded context budget" in first.content
    assert second.content == "B" * 2000 or second.metadata.get("tool_result_budget_compacted") is True


def test_agent_runtime_writes_truncated_tool_result_to_session_context() -> None:
    factory = LLMFactory.from_mapping(_model_document())
    llm_client = _LargeToolLoopLLMClient()
    factory.register_provider("deepseek", lambda config: llm_client, replace=True)
    tool_registry = ToolRegistry()
    tool_registry.register(_LargeOutputTool(), source="test")
    event_bus = EventBus()
    emitted_events: list[object] = []
    event_bus.subscribe(emitted_events.append)
    task = TaskFactory().create(RunParams(message="run large tool", model="tool-model"))

    async def run_test() -> None:
        runtime_context = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=factory,
            tool_registry=tool_registry,
        ).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        await runtime.run(task)

    anyio.run(run_test)

    tool_messages = [message for message in task.session.messages if message.role == "tool"]
    assert len(tool_messages) == 1
    assert len(tool_messages[0].content) < 20000
    assert "tool output exceeded context budget" in tool_messages[0].content
    assert tool_messages[0].metadata["tool_result_budget"]["truncated"] is True

    tool_result_events = [event for event in emitted_events if isinstance(event, ToolResultEvent)]
    assert len(tool_result_events) == 1
    assert tool_result_events[0].output == _LargeOutputTool.CONTENT
    assert tool_result_events[0].context_output == tool_messages[0].content
    assert tool_result_events[0].truncated is True


class _LargeToolLoopLLMClient(LLMClient):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            return LLMResponse(
                content="",
                tool_calls=[LLMToolCall(id="call-large", name="large_output", arguments={})],
                model="provider-model-id",
                provider="deepseek",
                finish_reason="tool_calls",
            )
        return LLMResponse(
            content="done",
            model="provider-model-id",
            provider="deepseek",
            finish_reason="stop",
        )


class _LargeOutputTool(Tool):
    name = "large_output"
    description = "Return a large output."
    CONTENT = "HEAD" + ("A" * 60000) + "TAIL"

    async def execute(self) -> ToolResult:
        return ToolResult(success=True, content=self.CONTENT)
