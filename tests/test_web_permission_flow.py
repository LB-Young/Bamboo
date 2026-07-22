"""Web permission approval flow tests."""

from __future__ import annotations

import anyio
from fastapi.testclient import TestClient

from bamboo.adapters.web.app import _event_payload, create_app
from bamboo.helpers.constant import (
    PermissionRequestEvent,
    ReasoningDeltaEvent,
    ReasoningFinishEvent,
    ReasoningStartEvent,
)
from bamboo.helpers.requests_params import RunParams
from bamboo.security import PermissionDecision, PermissionRequest, PermissionResult, WebPermissionResolver
from bamboo.security.permission_resolver import permission_request_id


def test_web_permission_resolver_allows_after_submit() -> None:
    resolver = WebPermissionResolver(timeout_seconds=1)
    request = _permission_request()
    result = PermissionResult(PermissionDecision.ASK, "write", "permission required", True)

    async def run_test() -> None:
        async with anyio.create_task_group() as task_group:
            outcome = {}

            async def wait_for_permission() -> None:
                outcome["result"] = await resolver.resolve(request, result, RunParams(platform="web"))

            task_group.start_soon(wait_for_permission)
            await anyio.sleep(0)
            accepted = await resolver.submit(permission_request_id(request), "allow")
            assert accepted is True

        resolved = outcome["result"]
        assert resolved.allowed
        assert resolved.reason == "user approved permission prompt"

    anyio.run(run_test)


def test_web_permission_resolver_accepts_decision_before_waiter_exists() -> None:
    resolver = WebPermissionResolver(timeout_seconds=1)
    request = _permission_request()
    result = PermissionResult(PermissionDecision.ASK, "write", "permission required", True)

    async def run_test() -> None:
        accepted = await resolver.submit(permission_request_id(request), "deny")
        assert accepted is True
        resolved = await resolver.resolve(request, result, RunParams(platform="web"))
        assert resolved.decision == PermissionDecision.DENY
        assert resolved.reason == "user denied permission prompt"

    anyio.run(run_test)


def test_web_permission_endpoint_submits_to_app_resolver() -> None:
    app = create_app()
    client = TestClient(app)
    request = _permission_request()
    request_id = permission_request_id(request)

    response = client.post(f"/api/permissions/{request_id}", json={"decision": "allow"})

    assert response.status_code == 200
    assert response.json() == {"accepted": True, "request_id": request_id, "decision": "allow"}

    async def run_test() -> None:
        resolved = await app.state.permission_resolver.resolve(
            request,
            PermissionResult(PermissionDecision.ASK, "write", "permission required", True),
            RunParams(platform="web"),
        )
        assert resolved.allowed

    anyio.run(run_test)


def test_web_permission_event_payload_includes_scoped_request_id() -> None:
    event = PermissionRequestEvent(
        session_id="session-1",
        task_id="task-1",
        tool_call_id="call-1",
        tool_name="write",
        risk_level="write",
        reason="permission required",
        requires_confirmation=True,
    )

    payload = _event_payload(event)

    assert payload["type"] == "permission_request"
    assert payload["request_id"] == "session-1:task-1:call-1"
    assert payload["session_id"] == "session-1"
    assert payload["task_id"] == "task-1"


def test_web_reasoning_event_payloads_are_separate_from_text() -> None:
    start = _event_payload(ReasoningStartEvent(session_id="session-1", task_id="task-1", message_id="message-1"))
    delta = _event_payload(ReasoningDeltaEvent(session_id="session-1", task_id="task-1", delta="推理过程"))
    finish = _event_payload(
        ReasoningFinishEvent(
            session_id="session-1",
            task_id="task-1",
            message_id="message-1",
            content="推理过程",
        )
    )

    assert start == {"type": "reasoning_start", "message_id": "message-1"}
    assert delta == {"type": "reasoning_delta", "text": "推理过程"}
    assert finish == {"type": "reasoning_finish", "text": "推理过程", "message_id": "message-1"}


def _permission_request() -> PermissionRequest:
    return PermissionRequest(
        session_id="session-1",
        task_id="task-1",
        tool_call_id="call-1",
        tool_name="write",
        arguments={"value": "data"},
        risk_level="write",
        source="test",
    )
