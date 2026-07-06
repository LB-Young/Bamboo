"""Tool permission policy for runtime execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bamboo.helpers.requests_params import RunParams
from bamboo.security.command_security import CommandRisk, inspect_command


class PermissionDecision(str, Enum):
    """Possible permission policy decisions."""

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PermissionRequest:
    """Information needed to decide whether a tool call may run."""

    session_id: str
    task_id: str
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    risk_level: str = "read"
    source: str = "builtin"
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PermissionResult:
    """Permission decision returned by policy."""

    decision: PermissionDecision
    risk_level: str
    reason: str
    requires_confirmation: bool = False

    @property
    def allowed(self) -> bool:
        """Return True when the tool call may run."""
        return self.decision == PermissionDecision.ALLOW


class PermissionPolicy:
    """Permission policy that classifies tool calls as allow, ask, or deny."""

    BYPASS_MODES = {"bypass", "yolo", "full-auto", "dangerously-skip-permissions"}
    READ_ONLY_MODES = {"deny", "read-only", "readonly"}
    DEFAULT_MODES = {"", "default", "auto", "strict"}

    def evaluate(self, request: PermissionRequest, run_params: RunParams) -> PermissionResult:
        """Evaluate a tool call against the current permission mode."""
        mode = (run_params.permission or "default").strip().lower()

        risk_level = request.risk_level or "read"
        reason = request.reason or f"tool risk={risk_level}"
        requires_confirmation = risk_level in {"write", "execute", "network", "unknown"}

        if request.tool_name == "bash":
            command_result = inspect_command(str(request.arguments.get("command", "")))
            risk_level = _risk_from_command(command_result.risk)
            reason = command_result.reason
            requires_confirmation = command_result.requires_confirmation
            if not command_result.allowed:
                return PermissionResult(
                    PermissionDecision.DENY,
                    risk_level,
                    reason,
                    requires_confirmation=True,
                )

        if request.tool_name == "browser":
            risk_level = _risk_from_browser_action(str(request.arguments.get("action", "")))
            reason = f"browser action={request.arguments.get('action', '') or 'unknown'} risk={risk_level}"
            requires_confirmation = risk_level in {"write", "network", "unknown"}

        if risk_level == "destructive":
            return PermissionResult(
                PermissionDecision.DENY,
                risk_level,
                reason or "destructive tool calls are always blocked",
                requires_confirmation=False,
            )

        if mode in self.BYPASS_MODES:
            return PermissionResult(PermissionDecision.ALLOW, risk_level, f"{mode} permission mode")

        if risk_level == "read":
            return PermissionResult(PermissionDecision.ALLOW, risk_level, reason)

        if mode in self.READ_ONLY_MODES:
            return PermissionResult(
                PermissionDecision.DENY,
                risk_level,
                f"permission mode {mode} only allows read tools",
                requires_confirmation=True,
            )

        if run_params.yes_all and mode in self.DEFAULT_MODES:
            return PermissionResult(PermissionDecision.ALLOW, risk_level, "--yes approved permission prompt")

        return PermissionResult(
            PermissionDecision.ASK,
            risk_level,
            f"permission required for {risk_level} tool",
            requires_confirmation=True,
        )


def _risk_from_command(risk: CommandRisk) -> str:
    if risk == CommandRisk.READ_ONLY:
        return "read"
    if risk == CommandRisk.WRITE:
        return "write"
    if risk == CommandRisk.NETWORK:
        return "network"
    if risk == CommandRisk.DESTRUCTIVE:
        return "destructive"
    return "unknown"


def _risk_from_browser_action(action: str) -> str:
    normalized = action.strip().lower()
    if normalized in {"extract_text", "screenshot", "wait_for", "close"}:
        return "read"
    if normalized == "open":
        return "network"
    if normalized in {"click", "type", "press"}:
        return "write"
    return "unknown"
