"""验证 Agent trace events、pattern 订阅和 LLM 脱敏事件。"""

from __future__ import annotations

import anyio

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import LLMRequestEvent, LLMResponseEvent, ToolCallEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMClient, LLMFactory, LLMRequest, LLMResponse
from bamboo.runtime.agent_runtime import AgentRuntime
from bamboo.runtime.runtime_context import RuntimeContextBuilder


def test_base_event_includes_parent_event_id() -> None:
    """验证事件可表达父子关系。"""
    event = ToolCallEvent(
        session_id="session-trace",
        task_id="task-trace",
        parent_event_id="parent-1",
        tool_name="echo",
    )

    assert event.to_dict()["parent_event_id"] == "parent-1"


def test_event_bus_pattern_subscription_matches_legacy_event_names() -> None:
    """验证 `tool.*` 能匹配当前兼容事件名 `tool-call`。"""
    event_bus = EventBus()
    received: list[str] = []
    event_bus.subscribe(lambda event: received.append(event.type), patterns="tool.*")

    async def run_test() -> None:
        await event_bus.emit(ToolCallEvent(session_id="session-trace", task_id="task-trace", tool_name="echo"))

    anyio.run(run_test)

    assert received == ["tool-call"]
    assert event_bus.count_subscribers("tool-result") == 1
    assert event_bus.count_subscribers("text-delta") == 0


def test_agent_runtime_emits_redacted_llm_trace_events() -> None:
    """验证主模型调用会发出脱敏 request/response trace，并建立 parent_event_id。"""
    event_bus = EventBus()
    events: list[object] = []
    event_bus.subscribe(events.append, patterns="llm.*")
    factory = LLMFactory.from_mapping(_model_document())
    llm_client = _StaticLLMClient()
    factory.register_provider("deepseek", lambda config: llm_client, replace=True)
    task = TaskFactory().create(RunParams(message="secret user content", model="trace-model"))

    async def run_test() -> None:
        runtime_context = RuntimeContextBuilder(event_bus=event_bus, llm_factory=factory).build(task)
        await AgentRuntime(runtime_context=runtime_context).run(task)

    anyio.run(run_test)

    llm_request = next(event for event in events if isinstance(event, LLMRequestEvent))
    llm_response = next(event for event in events if isinstance(event, LLMResponseEvent))
    assert llm_request.model_name == "trace-model"
    assert llm_request.provider == "deepseek"
    assert llm_request.message_count >= 1
    assert llm_request.input_chars > 0
    assert "secret user content" not in str(llm_request.to_dict())
    assert llm_response.parent_event_id == llm_request.event_id
    assert llm_response.success is True
    assert llm_response.output_chars == len("trace answer")
    assert "trace answer" not in str(llm_response.to_dict())


def test_trace_recorder_persists_llm_events(tmp_path, monkeypatch) -> None:
    """验证 TaskRuntime 的 events.jsonl 会包含 LLM 脱敏 trace。"""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    event_bus = EventBus()
    factory = LLMFactory.from_mapping(_model_document())
    llm_client = _StaticLLMClient()
    factory.register_provider("deepseek", lambda config: llm_client, replace=True)
    runtime = _runtime_with_factory(event_bus, factory)

    async def run_test() -> None:
        await runtime.run(
            RunParams(
                message="persist secret",
                model="trace-model",
                task_id="task-trace-events",
                session_id="session-trace-events",
            )
        )

    anyio.run(run_test)

    event_files = list((home_dir / ".bamboo" / "memory").rglob("events.jsonl"))
    assert len(event_files) == 1
    lines = event_files[0].read_text(encoding="utf-8").splitlines()
    llm_lines = [line for line in lines if "llm-request" in line or "llm-response" in line]
    assert any("llm-request" in line for line in llm_lines)
    assert any("llm-response" in line for line in llm_lines)
    assert all("persist secret" not in line for line in llm_lines)


def _model_document() -> dict:
    return {
        "default_model": "trace-model",
        "models": {
            "trace-model": {
                "provider": "deepseek",
                "model": "provider-model-id",
                "api_key": "test-api-key",
                "base_url": "https://llm.test/v1",
                "max_tokens": 128,
            }
        },
    }


def _runtime_with_factory(event_bus: EventBus, factory: LLMFactory):
    from bamboo.runtime.task_runtime import TaskRuntime

    return TaskRuntime(event_bus=event_bus, llm_factory=factory)


class _StaticLLMClient(LLMClient):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="trace answer",
            model="provider-model-id",
            provider="deepseek",
            finish_reason="stop",
        )
