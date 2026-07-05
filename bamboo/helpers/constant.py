"""Bamboo 运行时常量和事件类型定义。"""

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from bamboo.helpers.utils import BaseEvent



class SessionMode(str, enum.Enum):
    auto = "auto"
    project = "project"
    chat = "chat"



# ─── Text 事件 ────────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class TextStartEvent(BaseEvent):
    """助手开始输出文本"""
    type: str = "text-start"
    message_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {**super().to_dict(), "type": self.type, "message_id": self.message_id}


@dataclass(kw_only=True)
class TextDeltaEvent(BaseEvent):
    """文本增量（streaming）"""
    type: str = "text-delta"
    delta: str = ""

    def to_dict(self) -> dict:
        return {**super().to_dict(), "delta": self.delta}


@dataclass(kw_only=True)
class TextFinishEvent(BaseEvent):
    """文本输出完成"""
    type: str = "text-finish"
    content: str = ""
    message_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {**super().to_dict(), "content": self.content, "message_id": self.message_id}


# ─── Reasoning 事件 ───────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class ReasoningStartEvent(BaseEvent):
    type: str = "reasoning-start"
    message_id: Optional[str] = None


@dataclass(kw_only=True)
class ReasoningDeltaEvent(BaseEvent):
    type: str = "reasoning-delta"
    delta: str = ""

    def to_dict(self) -> dict:
        return {**super().to_dict(), "delta": self.delta}


@dataclass(kw_only=True)
class ReasoningFinishEvent(BaseEvent):
    type: str = "reasoning-finish"
    content: str = ""
    message_id: Optional[str] = None


# ─── Tool 事件 ────────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class ToolCallEvent(BaseEvent):
    """工具被调用"""
    type: str = "tool-call"
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    tool_call_id: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_call_id": self.tool_call_id,
        }


@dataclass(kw_only=True)
class ToolResultEvent(BaseEvent):
    """工具执行结果"""
    type: str = "tool-result"
    tool_name: str = ""
    tool_call_id: str = ""
    output: str = ""
    context_output: str = ""
    truncated: bool = False
    original_length: int = 0
    context_length: int = 0
    original_tokens: int = 0
    context_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "output": self.output,
            "context_output": self.context_output,
            "truncated": self.truncated,
            "original_length": self.original_length,
            "context_length": self.context_length,
            "original_tokens": self.original_tokens,
            "context_tokens": self.context_tokens,
        }


@dataclass(kw_only=True)
class ToolErrorEvent(BaseEvent):
    """工具执行出错"""
    type: str = "tool-error"
    tool_name: str = ""
    tool_call_id: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "error": self.error,
        }


@dataclass(kw_only=True)
class PermissionRequestEvent(BaseEvent):
    """工具权限请求事件。"""

    type: str = "permission-request"
    tool_name: str = ""
    tool_call_id: str = ""
    risk_level: str = "read"
    reason: str = ""
    requires_confirmation: bool = False

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass(kw_only=True)
class PermissionResultEvent(BaseEvent):
    """工具权限决策事件。"""

    type: str = "permission-result"
    tool_name: str = ""
    tool_call_id: str = ""
    decision: str = ""
    approved: bool = False
    risk_level: str = "read"
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "decision": self.decision,
            "approved": self.approved,
            "risk_level": self.risk_level,
            "reason": self.reason,
        }


@dataclass(kw_only=True)
class ToolAuditEvent(BaseEvent):
    """工具审计事件。"""

    type: str = "tool-audit"
    tool_name: str = ""
    tool_call_id: str = ""
    risk_level: str = "read"
    decision: str = ""
    approved: bool = False
    success: bool | None = None
    reason: str = ""
    error: str = ""
    duration_ms: int | None = None

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "approved": self.approved,
            "success": self.success,
            "reason": self.reason,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass(kw_only=True)
class TodoUpdateEvent(BaseEvent):
    """Todo 列表更新事件。"""

    type: str = "todo-update"
    todos: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {**super().to_dict(), "todos": self.todos, "counts": self.counts}


@dataclass(kw_only=True)
class TaskSnapshotEvent(BaseEvent):
    """任务快照事件。"""

    type: str = "task-snapshot"
    snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {**super().to_dict(), "snapshot": self.snapshot}


@dataclass(kw_only=True)
class TaskStopEvent(BaseEvent):
    """任务停止事件。"""

    type: str = "task-stop"
    stopped_task_id: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {**super().to_dict(), "stopped_task_id": self.stopped_task_id, "reason": self.reason}


@dataclass(kw_only=True)
class SubagentStartEvent(BaseEvent):
    """子 Agent 启动事件。"""

    type: str = "subagent-start"
    subagent_name: str = ""
    child_task_id: str = ""
    parent_session_id: str = ""
    parent_task_id: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "subagent_name": self.subagent_name,
            "child_task_id": self.child_task_id,
            "parent_session_id": self.parent_session_id,
            "parent_task_id": self.parent_task_id,
            "description": self.description,
        }


@dataclass(kw_only=True)
class SubagentFinishEvent(BaseEvent):
    """子 Agent 完成事件。"""

    type: str = "subagent-finish"
    subagent_name: str = ""
    child_task_id: str = ""
    child_session_id: str = ""
    parent_session_id: str = ""
    parent_task_id: str = ""
    status: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "subagent_name": self.subagent_name,
            "child_task_id": self.child_task_id,
            "child_session_id": self.child_session_id,
            "parent_session_id": self.parent_session_id,
            "parent_task_id": self.parent_task_id,
            "status": self.status,
        }


@dataclass(kw_only=True)
class KnowledgeUpdateEvent(BaseEvent):
    """Memory knowledge update event."""

    type: str = "memory-knowledge-update"
    scope: str = ""
    file: str = ""
    operation: str = ""
    status: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "scope": self.scope,
            "file": self.file,
            "operation": self.operation,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(kw_only=True)
class KnowledgeUpdateErrorEvent(BaseEvent):
    """Memory knowledge update error event."""

    type: str = "memory-knowledge-error"
    scope: str = ""
    file: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {**super().to_dict(), "scope": self.scope, "file": self.file, "reason": self.reason}


# ─── Step 事件 ───────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class StepStartEvent(BaseEvent):
    """步骤开始"""
    type: str = "step-start"
    step_id: str = ""
    step_index: int = 0

    def to_dict(self) -> dict:
        return {**super().to_dict(), "step_id": self.step_id, "step_index": self.step_index}


@dataclass(kw_only=True)
class StepFinishEvent(BaseEvent):
    """步骤完成"""
    type: str = "step-finish"
    step_id: str = ""
    step_index: int = 0
    summary: str = ""
    files_changed: list[str] = field(default_factory=list)
    token_used: int = 0

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "step_id": self.step_id,
            "step_index": self.step_index,
            "summary": self.summary,
            "files_changed": self.files_changed,
            "token_used": self.token_used,
        }


# ─── System 事件 ────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class SessionCompactEvent(BaseEvent):
    """会话上下文压缩"""
    type: str = "session-compact"
    before_token_count: int = 0
    after_token_count: int = 0

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "before_token_count": self.before_token_count,
            "after_token_count": self.after_token_count,
        }


@dataclass(kw_only=True)
class SessionStatusChangeEvent(BaseEvent):
    """会话状态变化"""
    type: str = "session-status-change"
    status: str = "idle"
    reason: str = ""

    def to_dict(self) -> dict:
        return {**super().to_dict(), "status": self.status, "reason": self.reason}


@dataclass(kw_only=True)
class AuditEvent(BaseEvent):
    """审计日志事件"""
    type: str = "audit"
    action: str = ""
    tool_name: Optional[str] = None
    params: dict = field(default_factory=dict)
    result: str = ""
    approved: bool = True

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "action": self.action,
            "tool_name": self.tool_name,
            "params": self.params,
            "result": self.result,
            "approved": self.approved,
        }


# ─── Plan 事件 ────────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class PlanStartEvent(BaseEvent):
    """规划开始"""
    type: str = "plan-start"
    plan_id: str = ""
    task: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "plan_id": self.plan_id,
            "task": self.task,
        }


@dataclass(kw_only=True)
class PlanConfirmEvent(BaseEvent):
    """用户确认计划"""
    type: str = "plan-confirm"
    plan_id: str = ""
    step_count: int = 0

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "plan_id": self.plan_id,
            "step_count": self.step_count,
        }


@dataclass(kw_only=True)
class PlanStepExecuteEvent(BaseEvent):
    """计划步骤执行"""
    type: str = "plan-step"
    plan_id: str = ""
    step_index: int = 0
    step_description: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "plan_id": self.plan_id,
            "step_index": self.step_index,
            "step_description": self.step_description,
        }


@dataclass(kw_only=True)
class PlanCancelEvent(BaseEvent):
    """用户取消计划"""
    type: str = "plan-cancel"
    plan_id: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "plan_id": self.plan_id,
            "reason": self.reason,
        }


# ─── Workflow 事件 ────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class WorkflowRunStartEvent(BaseEvent):
    """工作流执行开始"""
    type: str = "workflow-run-start"
    run_id: str = ""
    workflow_id: str = ""

    def to_dict(self) -> dict:
        return {**super().to_dict(), "run_id": self.run_id, "workflow_id": self.workflow_id}


@dataclass(kw_only=True)
class WorkflowRunCompleteEvent(BaseEvent):
    """工作流执行完成"""
    type: str = "workflow-run-complete"
    run_id: str = ""
    workflow_id: str = ""
    status: str = ""  # completed / failed / cancelled
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
        }


@dataclass(kw_only=True)
class WorkflowBreakpointEvent(BaseEvent):
    """工作流触发断点"""
    type: str = "workflow-breakpoint"
    run_id: str = ""
    workflow_id: str = ""
    step_id: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "reason": self.reason,
        }


# ─── Task 事件 ────────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class TaskCreateEvent(BaseEvent):
    """任务创建"""
    type: str = "task-create"
    task_id: str = ""
    title: str = ""

    def to_dict(self) -> dict:
        return {**super().to_dict(), "task_id": self.task_id, "title": self.title}


@dataclass(kw_only=True)
class TaskStatusChangeEvent(BaseEvent):
    """任务状态变化"""
    type: str = "task-status-change"
    task_id: str = ""
    from_status: str = ""
    to_status: str = ""

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "task_id": self.task_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
        }


# ─── 类型别名 ────────────────────────────────────────────────────────────────

BambooEvent = (
    TextStartEvent | TextDeltaEvent | TextFinishEvent
    | ReasoningStartEvent | ReasoningDeltaEvent | ReasoningFinishEvent
    | ToolCallEvent | ToolResultEvent | ToolErrorEvent
    | PermissionRequestEvent | PermissionResultEvent | ToolAuditEvent
    | SubagentStartEvent | SubagentFinishEvent
    | KnowledgeUpdateEvent | KnowledgeUpdateErrorEvent
    | StepStartEvent | StepFinishEvent
    | SessionCompactEvent | SessionStatusChangeEvent | AuditEvent
    | PlanStartEvent | PlanConfirmEvent | PlanStepExecuteEvent | PlanCancelEvent
    | TaskCreateEvent | TaskStatusChangeEvent
    | WorkflowRunStartEvent | WorkflowRunCompleteEvent | WorkflowBreakpointEvent
)
