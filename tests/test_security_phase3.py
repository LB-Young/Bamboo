"""Phase 3 security policy, permission, and audit tests."""

from __future__ import annotations

import json

import anyio

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import PermissionResultEvent, ToolAuditEvent, ToolErrorEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMClient, LLMFactory, LLMRequest, LLMResponse, LLMToolCall
from bamboo.security import (
    NonInteractivePermissionResolver,
    PermissionDecision,
    PermissionPolicy,
    PermissionRequest,
    PermissionResolver,
    PermissionResult,
    ToolAuditLogger,
    ToolAuditRecord,
    inspect_command,
)
from bamboo.security.command_security import CommandRisk
from bamboo.runtime.agent_runtime import AgentRuntime
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.tools.buildin.bash import BashTool
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


def test_command_security_classifies_read_write_network_and_destructive() -> None:
    assert inspect_command("git status").risk == CommandRisk.READ_ONLY
    assert inspect_command("touch created.txt").risk == CommandRisk.WRITE
    assert inspect_command("curl https://example.com").risk == CommandRisk.NETWORK

    destructive = inspect_command("rm -rf /")
    assert not destructive.allowed
    assert destructive.risk == CommandRisk.DESTRUCTIVE


def test_permission_policy_allows_read_and_requires_yes_for_write() -> None:
    policy = PermissionPolicy()
    request = PermissionRequest(
        session_id="s1",
        task_id="t1",
        tool_call_id="c1",
        tool_name="bash",
        arguments={"command": "touch created.txt"},
        risk_level="execute",
    )

    ask = policy.evaluate(request, RunParams(permission="default", yes_all=False))
    assert ask.decision == PermissionDecision.ASK
    assert ask.risk_level == "write"

    approved = policy.evaluate(request, RunParams(permission="default", yes_all=True))
    assert approved.allowed
    assert approved.risk_level == "write"

    read = policy.evaluate(
        PermissionRequest(
            session_id="s1",
            task_id="t1",
            tool_call_id="c2",
            tool_name="bash",
            arguments={"command": "git status"},
            risk_level="execute",
        ),
        RunParams(permission="default", yes_all=False),
    )
    assert read.allowed
    assert read.risk_level == "read"


def test_tool_audit_logger_writes_redacted_jsonl(tmp_path) -> None:
    audit_path = tmp_path / "audit" / "tool_calls.jsonl"
    logger = ToolAuditLogger(audit_path)
    logger.append(
        ToolAuditRecord(
            session_id="s1",
            task_id="t1",
            tool_call_id="c1",
            tool_name="api_tool",
            risk_level="network",
            decision="allow",
            approved=True,
            arguments={"api_key": "secret", "nested": {"token": "token-value"}},
            success=True,
            output_preview="ok",
        )
    )

    payload = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert payload["arguments"]["api_key"] == "[REDACTED]"
    assert payload["arguments"]["nested"]["token"] == "[REDACTED]"


def test_agent_runtime_denies_unapproved_bash_write_and_audits(tmp_path) -> None:
    factory = LLMFactory.from_mapping(_model_document())
    llm_client = _BashWriteThenDoneLLMClient(
        tool_name="bash",
        tool_arguments={"command": "touch created.txt"},
    )
    factory.register_provider("deepseek", lambda config: llm_client, replace=True)
    registry = ToolRegistry()
    registry.register(BashTool(), source="buildin")
    event_bus = EventBus()
    emitted_events: list[object] = []
    event_bus.subscribe(emitted_events.append)
    task = TaskFactory().create(
        RunParams(message="create a file", model="test-model", permission="default", yes_all=False)
    )

    async def run_test() -> None:
        runtime_context = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=factory,
            tool_registry=registry,
            permission_resolver=NonInteractivePermissionResolver(),
            audit_logger=ToolAuditLogger(tmp_path / "tool_audit.jsonl"),
        ).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        completed_task = await runtime.run(task)
        assert completed_task.output == "done"

    anyio.run(run_test)

    assert any(
        isinstance(event, PermissionResultEvent) and event.approved is False and event.risk_level == "write"
        for event in emitted_events
    )
    assert any(isinstance(event, ToolErrorEvent) and "Tool call denied" in event.error for event in emitted_events)
    assert any(isinstance(event, ToolAuditEvent) and event.approved is False for event in emitted_events)
    audit_payload = json.loads((tmp_path / "tool_audit.jsonl").read_text(encoding="utf-8").strip())
    assert audit_payload["approved"] is False
    assert audit_payload["success"] is False


def test_agent_runtime_executes_ask_tool_after_resolver_approval(tmp_path) -> None:
    factory = LLMFactory.from_mapping(_model_document())
    llm_client = _BashWriteThenDoneLLMClient(
        tool_name="write_record",
        tool_arguments={"value": "data"},
    )
    factory.register_provider("deepseek", lambda config: llm_client, replace=True)
    registry = ToolRegistry()
    registry.register(_RecordingWriteTool(), source="test")
    event_bus = EventBus()
    emitted_events: list[object] = []
    event_bus.subscribe(emitted_events.append)
    task = TaskFactory().create(
        RunParams(message="write data", model="test-model", permission="default", yes_all=False)
    )

    async def run_test() -> None:
        runtime_context = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=factory,
            tool_registry=registry,
            permission_resolver=_ApprovingResolver(),
            audit_logger=ToolAuditLogger(tmp_path / "tool_audit_approved.jsonl"),
        ).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        completed_task = await runtime.run(task)
        assert completed_task.output == "done"

    anyio.run(run_test)

    assert any(
        isinstance(event, PermissionResultEvent) and event.approved is True and event.decision == "allow"
        for event in emitted_events
    )
    payload = json.loads((tmp_path / "tool_audit_approved.jsonl").read_text(encoding="utf-8").strip())
    assert payload["approved"] is True
    assert payload["success"] is True


class _BashWriteThenDoneLLMClient(LLMClient):
    def __init__(self, *, tool_name: str, tool_arguments: dict) -> None:
        self.tool_name = tool_name
        self.tool_arguments = tool_arguments
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            return LLMResponse(
                content="",
                model="provider-model-id",
                provider="deepseek",
                finish_reason="tool_calls",
                tool_calls=[
                    LLMToolCall(
                        id="call-bash-1",
                        name=self.tool_name,
                        arguments=self.tool_arguments,
                    )
                ],
            )
        return LLMResponse(
            content="done",
            model="provider-model-id",
            provider="deepseek",
            finish_reason="stop",
        )


class _ApprovingResolver(PermissionResolver):
    async def resolve(
        self,
        request: PermissionRequest,
        result: PermissionResult,
        run_params: RunParams,
    ) -> PermissionResult:
        if result.decision == PermissionDecision.ASK:
            return PermissionResult(
                PermissionDecision.ALLOW,
                result.risk_level,
                "test approved",
                requires_confirmation=result.requires_confirmation,
            )
        return result


class _RecordingWriteTool:
    name = "write_record"
    description = "Record a write operation."
    risk_level = "write"
    tags = ("test",)
    is_builtin = False

    def input_schema(self) -> dict:
        return {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema()}

    async def execute(self, value: str) -> object:
        from bamboo.tools.buildin.base import ToolResult

        return ToolResult(content=f"recorded: {value}", success=True)
