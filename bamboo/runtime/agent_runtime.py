"""带可恢复错误处理和真实模型调用的 OTA Agent 运行时。

Agent 按 Observe -> Think -> Act 循环运行，并在 Act 阶段通过统一
LLMFactory 调用 models.yaml 中注册的模型。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import (
    AuditEvent,
    PermissionRequestEvent,
    PermissionResultEvent,
    SessionCompactEvent,
    SessionStatusChangeEvent,
    TextDeltaEvent,
    TextFinishEvent,
    TextStartEvent,
    ToolAuditEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
)
from bamboo.llms import LLMResponse, LLMToolCall
from bamboo.runtime.prompt import AgentPrompt
from bamboo.runtime.runtime_context import RuntimeContext
from bamboo.runtime.state_machine import AgentState, AgentStateMachine
from bamboo.runtime.tool_result_budget import ToolResultBudgeter
from bamboo.security import PermissionDecision, PermissionRequest, PermissionResult, ToolAuditRecord


@dataclass(slots=True)
class AgentRecoveryPolicy:
    """配置 Agent 单次循环错误后的恢复策略。"""

    max_iterations: int = 50
    max_recoverable_errors: int = 5
    continue_after_error: bool = True


@dataclass(slots=True)
class AgentRunState:
    """记录一次 Agent 运行中的循环次数和可恢复错误。"""

    iteration: int = 0
    compaction_count: int = 0
    recoverable_errors: list[str] = field(default_factory=list)


class AgentRuntimeError(RuntimeError):
    """表示 Agent 已耗尽恢复预算。"""


class AgentRuntime:
    """运行 OTA 循环，并在可恢复错误后继续。"""

    def __init__(
        self,
        *,
        runtime_context: RuntimeContext,
        state_machine: AgentStateMachine | None = None,
        recovery_policy: AgentRecoveryPolicy | None = None,
    ) -> None:
        """初始化 Agent 执行状态，并接收已装配好的运行上下文。"""
        self.runtime_context = runtime_context
        self.event_bus = runtime_context.event_bus
        self.state_machine = state_machine or AgentStateMachine()
        self.tool_registry = runtime_context.tool_registry
        self.prompt_builder = runtime_context.prompt_builder
        self.recovery_policy = recovery_policy or AgentRecoveryPolicy()
        self.llm_factory = runtime_context.llm_factory
        self.model_name = runtime_context.model_name
        self.compaction_model_name = runtime_context.compaction_model_name
        self.model_config = runtime_context.model_config
        self.llm_client = runtime_context.llm_client
        self.compaction_llm_client = runtime_context.compaction_llm_client
        self.context_compactor = runtime_context.context_compactor
        self.permission_policy = runtime_context.permission_policy
        self.permission_resolver = runtime_context.permission_resolver
        self.audit_logger = runtime_context.audit_logger
        self.tool_result_budgeter = ToolResultBudgeter()
        self.run_state = AgentRunState()

    async def run(self, task: Task) -> Task:
        """执行 OTA 循环，直到完成或恢复预算耗尽。"""
        while self.run_state.iteration < self.recovery_policy.max_iterations:
            self.run_state.iteration += 1
            try:
                completed = await self._run_one_cycle(task)
                if completed:
                    return task
            except Exception as exc:
                # 单轮失败不立刻让任务失败，先尝试把错误写入上下文并继续下一轮。
                if not await self._recover(task, exc):
                    await self._transition(task, AgentState.FAILED, "agent recovery exhausted")
                    raise AgentRuntimeError(str(exc)) from exc

        await self._transition(task, AgentState.FAILED, "agent max iterations exhausted")
        raise AgentRuntimeError("Agent max iterations exhausted")

    async def _run_one_cycle(self, task: Task) -> bool:
        """执行一轮 Observe -> Think -> Act，并返回任务是否已经完成。"""
        await self._transition(task, AgentState.OBSERVING, "collect context")
        observation = self._observe(task)
        observation = await self._compact_context_if_needed(task, observation)

        await self._transition(task, AgentState.THINKING, "call model and produce decision")
        thought = await self._think(task, observation)

        await self._transition(task, AgentState.ACTING, "apply model decision")
        completed = await self._act(task, thought)

        if completed:
            await self._transition(task, AgentState.COMPLETED, "agent completed")
        return completed

    def _observe(self, task: Task) -> AgentPrompt:
        """收集本轮 Agent 需要观察的上下文。"""
        return self.prompt_builder.build(
            task.session,
            error_history=self.run_state.recoverable_errors,
        )

    async def _think(self, task: Task, observation: AgentPrompt) -> LLMResponse:
        """调用主模型分析当前观察结果，并返回可供 Act 执行的模型决策。"""
        if task.metadata.pop("inject_agent_error_once", "") == "thinking":
            raise RuntimeError("Injected mock thinking error")
        response = await self.llm_client.complete(observation.to_llm_request())
        return response

    async def _compact_context_if_needed(self, task: Task, prompt: AgentPrompt) -> AgentPrompt:
        """在模型调用前按上下文预算压缩 Session，并返回重建后的 Prompt。"""
        current_prompt = prompt
        for _ in range(self.context_compactor.policy.max_compaction_passes):
            budget = self.context_compactor.evaluate(current_prompt)
            if not budget.should_compact:
                break
            if not self.context_compactor.has_compactable_messages(task.session):
                break

            await self._transition(
                task,
                AgentState.COMPACTING,
                (
                    f"compact context input_tokens={budget.input_tokens} "
                    f"remaining_tokens={budget.remaining_tokens}"
                ),
            )
            compacted = await self.context_compactor.compact(task.session)
            await self._transition(task, AgentState.OBSERVING, "rebuild context after compaction")
            if not compacted:
                break

            rebuilt_prompt = self._observe(task)
            rebuilt_budget = self.context_compactor.evaluate(rebuilt_prompt)
            self.run_state.compaction_count += 1
            task.metadata["context_compaction_count"] = str(self.run_state.compaction_count)
            task.metadata["context_compaction_model"] = self.compaction_model_name
            await self.event_bus.emit(
                SessionCompactEvent(
                    session_id=task.session_id,
                    task_id=task.task_id,
                    before_token_count=budget.input_tokens,
                    after_token_count=rebuilt_budget.input_tokens,
                )
            )
            current_prompt = rebuilt_prompt
            if rebuilt_budget.input_tokens >= budget.input_tokens:
                break
        return current_prompt

    async def _act(self, task: Task, decision: LLMResponse) -> bool:
        """执行模型的 Tool Calls；没有 Tool Call 时写入最终回答并结束任务。"""
        if task.metadata.pop("inject_agent_error_once", "") == "acting":
            raise RuntimeError("Injected mock acting error")

        if decision.tool_calls:
            task.session.add_message(
                "assistant",
                decision.content,
                agent_name=f"llm:{self.model_name}",
                tool_calls=list(decision.tool_calls),
            )
            await self._transition(task, AgentState.TOOL_CALLING, "execute model tool calls")
            for tool_call in decision.tool_calls:
                await self._execute_tool_call(task, tool_call)
            current_count = int(task.metadata.get("tool_call_count", "0"))
            task.metadata["tool_call_count"] = str(current_count + len(decision.tool_calls))
            return False

        content = decision.content

        message = task.session.add_message("assistant", content, agent_name=f"llm:{self.model_name}")
        await self.event_bus.emit(
            TextStartEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                message_id=message.message_id,
            )
        )
        await self.event_bus.emit(
            TextDeltaEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                delta=content,
            )
        )
        await self.event_bus.emit(
            TextFinishEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                message_id=message.message_id,
                content=content,
            )
        )
        task.output = content
        task.metadata["llm_model_name"] = self.model_name
        task.metadata["llm_model"] = decision.model
        task.metadata["llm_provider"] = decision.provider
        return True

    async def _execute_tool_call(self, task: Task, tool_call: LLMToolCall) -> None:
        """执行一条模型 Tool Call，并把结果或错误写回 Session 与 EventBus。"""
        await self.event_bus.emit(
            ToolCallEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                tool_name=tool_call.name,
                tool_input=tool_call.arguments,
                tool_call_id=tool_call.id,
            )
        )

        tool = self.tool_registry.get(tool_call.name)
        if tool is None:
            await self._record_tool_error(task, tool_call, f"Tool is unavailable: {tool_call.name}")
            return
        bind_runtime_context = getattr(tool, "bind_runtime_context", None)
        if callable(bind_runtime_context):
            bind_runtime_context(runtime_context=self.runtime_context, task=task)

        permission = await self._authorize_tool_call(task, tool_call)
        if not permission.allowed:
            await self._audit_tool_call(
                task,
                tool_call,
                permission,
                success=False,
                error=permission.reason,
            )
            await self._record_tool_error(task, tool_call, f"Tool call denied: {permission.reason}")
            return

        started_at = time.perf_counter()
        try:
            result = await tool.execute(**tool_call.arguments)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            await self._audit_tool_call(
                task,
                tool_call,
                permission,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )
            await self._record_tool_error(task, tool_call, f"Tool execution raised: {exc}")
            return

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        if not result.success:
            error = result.error or result.content or "Tool execution failed"
            await self._audit_tool_call(
                task,
                tool_call,
                permission,
                success=False,
                error=error,
                duration_ms=duration_ms,
                output_preview=result.content,
            )
            await self._record_tool_error(task, tool_call, error)
            return

        await self._audit_tool_call(
            task,
            tool_call,
            permission,
            success=True,
            duration_ms=duration_ms,
            output_preview=result.content,
        )
        budgeted_result = self.tool_result_budgeter.prepare_for_session(result.content)
        task.session.add_message(
            "tool",
            budgeted_result.context_content,
            agent_name=tool_call.name,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            metadata={
                "tool_result_budget": budgeted_result.metadata,
            },
        )
        self.tool_result_budgeter.compact_old_tool_results(task.session)
        await self.event_bus.emit(
            ToolResultEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                output=result.content,
                context_output=budgeted_result.context_content,
                truncated=budgeted_result.truncated,
                original_length=budgeted_result.original_length,
                context_length=budgeted_result.context_length,
                original_tokens=budgeted_result.original_tokens,
                context_tokens=budgeted_result.context_tokens,
            )
        )

    async def _authorize_tool_call(self, task: Task, tool_call: LLMToolCall) -> PermissionResult:
        """Run permission policy and emit permission lifecycle events."""
        metadata = self.tool_registry.get_metadata(tool_call.name)
        request = PermissionRequest(
            session_id=task.session_id,
            task_id=task.task_id,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            arguments=dict(tool_call.arguments),
            risk_level=metadata.risk_level if metadata is not None else "read",
            source=metadata.source if metadata is not None else "unknown",
        )
        policy_result = (
            self.permission_policy.evaluate(request, task.run_params)
            if self.permission_policy is not None
            else PermissionResult(PermissionDecision.ALLOW, request.risk_level, "permission policy disabled")
        )
        await self.event_bus.emit(
            PermissionRequestEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                risk_level=policy_result.risk_level,
                reason=policy_result.reason,
                requires_confirmation=policy_result.requires_confirmation,
            )
        )
        permission = (
            await self.permission_resolver.resolve(request, policy_result, task.run_params)
            if self.permission_resolver is not None
            else policy_result
        )
        await self.event_bus.emit(
            PermissionResultEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                decision=permission.decision.value,
                approved=permission.allowed,
                risk_level=permission.risk_level,
                reason=permission.reason,
            )
        )
        return permission

    async def _audit_tool_call(
        self,
        task: Task,
        tool_call: LLMToolCall,
        permission: PermissionResult,
        *,
        success: bool,
        error: str = "",
        duration_ms: int | None = None,
        output_preview: str = "",
    ) -> None:
        """Persist and emit a tool audit record."""
        record = ToolAuditRecord(
            session_id=task.session_id,
            task_id=task.task_id,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            risk_level=permission.risk_level,
            decision=permission.decision.value,
            approved=permission.allowed,
            reason=permission.reason,
            arguments=dict(tool_call.arguments),
            success=success,
            error=error,
            duration_ms=duration_ms,
            output_preview=output_preview,
        )
        if self.audit_logger is not None:
            self.audit_logger.append(record)
        await self.event_bus.emit(
            ToolAuditEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                risk_level=permission.risk_level,
                decision=permission.decision.value,
                approved=permission.allowed,
                success=success,
                reason=permission.reason,
                error=error,
                duration_ms=duration_ms,
            )
        )

    async def _record_tool_error(self, task: Task, tool_call: LLMToolCall, error: str) -> None:
        """记录可反馈给模型的工具错误，并发布 ToolErrorEvent。"""
        task.session.add_message(
            "tool",
            f"[tool-error]\n{error}",
            agent_name=tool_call.name,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
        )
        await self.event_bus.emit(
            ToolErrorEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                error=error,
            )
        )

    async def _recover(self, task: Task, exc: Exception) -> bool:
        """记录 Agent 可恢复错误，并在策略允许时继续循环。"""
        error = f"iteration={self.run_state.iteration} state={self.state_machine.state.value}: {exc}"
        self.run_state.recoverable_errors.append(error)
        # 将错误作为 system message 注入，下一轮 Observe 会把它组织进 prompt。
        task.session.add_message("system", f"[recoverable-agent-error]\n{error}", agent_name="runtime")
        task.metadata["last_agent_error"] = error

        await self.event_bus.emit(
            AuditEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                action="agent_error_recovered",
                result=error,
                approved=True,
            )
        )

        can_continue = (
            self.recovery_policy.continue_after_error
            and len(self.run_state.recoverable_errors) <= self.recovery_policy.max_recoverable_errors
        )
        if not can_continue:
            return False

        if self.state_machine.can_transition(AgentState.RECOVERING):
            await self._transition(task, AgentState.RECOVERING, "recover from agent error")
        return True

    async def _transition(self, task: Task, next_state: AgentState, reason: str) -> None:
        """推进 Agent 状态机，并发布 session 状态事件。"""
        _, new_state = self.state_machine.transition(next_state)
        await self.event_bus.emit(
            SessionStatusChangeEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                status=new_state.value,
                reason=reason,
            )
        )
