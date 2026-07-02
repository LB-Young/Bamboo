"""Permission resolvers for interactive and non-interactive runtimes."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

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


def create_permission_resolver(run_params: RunParams) -> PermissionResolver:
    """Create the default resolver for a runtime entrypoint."""
    if (run_params.platform or "").lower() == "cli":
        return ConsolePermissionResolver()
    return NonInteractivePermissionResolver()


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
