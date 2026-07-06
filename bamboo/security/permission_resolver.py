"""Permission resolvers for interactive and non-interactive runtimes."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from typing import Literal

from bamboo.helpers.requests_params import RunParams
from bamboo.security.permission_policy import PermissionDecision, PermissionRequest, PermissionResult


class PermissionResolver:
    """Resolve ask-style permission decisions."""

    async def resolve(
        self,
        request: PermissionRequest,
        result: PermissionResult,
        run_params: RunParams,
    ) -> PermissionResult:
        """Return a final allow or deny decision."""
        if result.decision != PermissionDecision.ASK:
            return result
        return replace(result, decision=PermissionDecision.DENY, reason="permission resolver did not approve request")


class NonInteractivePermissionResolver(PermissionResolver):
    """Deny ask decisions when no interactive approval channel is available."""

    async def resolve(
        self,
        request: PermissionRequest,
        result: PermissionResult,
        run_params: RunParams,
    ) -> PermissionResult:
        """Deny ask decisions without blocking execution."""
        if result.decision != PermissionDecision.ASK:
            return result
        return replace(result, decision=PermissionDecision.DENY, reason="interactive permission approval unavailable")


class ConsolePermissionResolver(PermissionResolver):
    """Ask the user in the terminal for permission to run a tool call."""

    async def resolve(
        self,
        request: PermissionRequest,
        result: PermissionResult,
        run_params: RunParams,
    ) -> PermissionResult:
        """Prompt the user for y/n approval."""
        if result.decision != PermissionDecision.ASK:
            return result

        prompt = _format_prompt(request, result)
        answer = await asyncio.to_thread(input, prompt)
        normalized = answer.strip().lower()
        if normalized in {"y", "yes", "allow", "a"}:
            return replace(result, decision=PermissionDecision.ALLOW, reason="user approved permission prompt")
        return replace(result, decision=PermissionDecision.DENY, reason="user denied permission prompt")


class WebPermissionResolver(PermissionResolver):
    """Wait for Web UI approval for ask-style permission decisions."""

    def __init__(self, *, timeout_seconds: float = 300.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._pending: dict[str, asyncio.Future[Literal["allow", "deny"]]] = {}
        self._decisions: dict[str, Literal["allow", "deny"]] = {}
        self._lock = asyncio.Lock()

    async def resolve(
        self,
        request: PermissionRequest,
        result: PermissionResult,
        run_params: RunParams,
    ) -> PermissionResult:
        """Wait until the Web client approves or denies the permission request."""
        if result.decision != PermissionDecision.ASK:
            return result

        request_id = permission_request_id(request)
        async with self._lock:
            decision = self._decisions.pop(request_id, None)
            if decision is None:
                future = asyncio.get_running_loop().create_future()
                self._pending[request_id] = future
            else:
                future = None

        if decision is None and future is not None:
            try:
                decision = await asyncio.wait_for(future, timeout=self.timeout_seconds)
            except asyncio.TimeoutError:
                decision = "deny"
                reason = "web permission approval timed out"
            else:
                reason = "user approved permission prompt" if decision == "allow" else "user denied permission prompt"
            finally:
                async with self._lock:
                    self._pending.pop(request_id, None)
                    self._decisions.pop(request_id, None)
        else:
            reason = "user approved permission prompt" if decision == "allow" else "user denied permission prompt"

        if decision == "allow":
            return replace(result, decision=PermissionDecision.ALLOW, reason=reason)
        return replace(result, decision=PermissionDecision.DENY, reason=reason)

    async def submit(
        self,
        request_id: str,
        decision: Literal["allow", "deny"],
    ) -> bool:
        """Submit a Web approval decision. Returns True when the request id is accepted."""
        if decision not in {"allow", "deny"}:
            return False
        async with self._lock:
            future = self._pending.get(request_id)
            if future is not None:
                if not future.done():
                    future.set_result(decision)
                return True
            self._decisions[request_id] = decision
            return True

    async def pending_count(self) -> int:
        """Return the number of pending Web approvals."""
        async with self._lock:
            return len(self._pending)


def create_permission_resolver(run_params: RunParams) -> PermissionResolver:
    """Create the default resolver for a runtime entrypoint."""
    if (run_params.platform or "").lower() == "cli":
        return ConsolePermissionResolver()
    return NonInteractivePermissionResolver()


def permission_request_id(request: PermissionRequest) -> str:
    """Build a stable id for a permission request."""
    return f"{request.session_id}:{request.task_id}:{request.tool_call_id}"


def _format_prompt(request: PermissionRequest, result: PermissionResult) -> str:
    arguments = json.dumps(request.arguments, ensure_ascii=False, sort_keys=True)
    return (
        "\nBamboo needs permission to run a tool.\n"
        f"tool: {request.tool_name}\n"
        f"risk: {result.risk_level}\n"
        f"reason: {result.reason}\n"
        f"arguments: {arguments}\n"
        "Allow? [y/N] "
    )
