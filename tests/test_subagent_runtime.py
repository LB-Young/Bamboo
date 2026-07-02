"""Subagent runtime and tool tests."""

from __future__ import annotations

import anyio

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import SubagentFinishEvent, SubagentStartEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMClient, LLMFactory, LLMRequest, LLMResponse
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.runtime.subagent_runtime import SubagentRuntime
from bamboo.subagents.registry import SubagentRegistry
from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.buildin.subagent_run import SubagentRunTool
from bamboo.tools.registry import ToolRegistry


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


def test_subagent_runtime_uses_restricted_tool_registry(tmp_path) -> None:
    factory = LLMFactory.from_mapping(_model_document())
    llm_client = _RecordingLLMClient()
    factory.register_provider("deepseek", lambda config: llm_client, replace=True)
    event_bus = EventBus()
    emitted: list[object] = []
    event_bus.subscribe(emitted.append)
    parent_task = TaskFactory().create(RunParams(message="parent", model="test-model", project=str(tmp_path)))
    tool_registry = ToolRegistry()
    tool_registry.register(_NamedTool("read"), source="test")
    tool_registry.register(_NamedTool("write", risk_level="write"), source="test")
    subagent_dir = tmp_path / "subagents"
    subagent_dir.mkdir()
    (subagent_dir / "explorer.yaml").write_text(
        "name: explorer\ndescription: Explore.\ntools:\n  read: true\n  write: false\n",
        encoding="utf-8",
    )
    subagent_registry = SubagentRegistry(subagent_dirs=[("test", subagent_dir)])
    parent_context = RuntimeContextBuilder(
        event_bus=event_bus,
        llm_factory=factory,
        tool_registry=tool_registry,
        subagent_registry=subagent_registry,
        mcp_enabled=False,
    ).build(parent_task)

    async def run_test() -> None:
        result = await SubagentRuntime(
            parent_context=parent_context,
            parent_task=parent_task,
            registry=subagent_registry,
        ).run(subagent_type="explorer", description="find files", prompt="summarize")
        assert result.output == "subagent summary"

    anyio.run(run_test)

    assert len(llm_client.requests) == 1
    assert [tool["name"] for tool in llm_client.requests[0].tools] == ["read"]
    assert any(isinstance(event, SubagentStartEvent) for event in emitted)
    assert any(isinstance(event, SubagentFinishEvent) for event in emitted)


def test_subagent_run_tool_returns_task_result(tmp_path) -> None:
    factory = LLMFactory.from_mapping(_model_document())
    llm_client = _RecordingLLMClient()
    factory.register_provider("deepseek", lambda config: llm_client, replace=True)
    parent_task = TaskFactory().create(RunParams(message="parent", model="test-model", project=str(tmp_path)))
    tool_registry = ToolRegistry()
    tool_registry.register(_NamedTool("read"), source="test")
    subagent_dir = tmp_path / "subagents"
    subagent_dir.mkdir()
    (subagent_dir / "explorer.yaml").write_text(
        "name: explorer\ndescription: Explore.\ntools:\n  read: true\n",
        encoding="utf-8",
    )
    subagent_registry = SubagentRegistry(subagent_dirs=[("test", subagent_dir)])
    parent_context = RuntimeContextBuilder(
        event_bus=EventBus(),
        llm_factory=factory,
        tool_registry=tool_registry,
        subagent_registry=subagent_registry,
        mcp_enabled=False,
    ).build(parent_task)
    tool = SubagentRunTool(subagent_registry=subagent_registry)
    tool.bind_runtime_context(runtime_context=parent_context, task=parent_task)

    async def run_test() -> None:
        result = await tool.execute(
            subagent_type="explorer",
            description="explore",
            prompt="summarize code",
        )
        assert result.success is True
        assert '<task_result subagent="explorer"' in result.content
        assert "subagent summary" in result.content

    anyio.run(run_test)


class _RecordingLLMClient(LLMClient):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            content="subagent summary",
            model="provider-model-id",
            provider="deepseek",
            finish_reason="stop",
        )


class _NamedTool(Tool):
    description = "named test tool"

    def __init__(self, name: str, *, risk_level: str = "read") -> None:
        self.name = name
        self.risk_level = risk_level

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(content="ok")
