"""带可恢复错误处理和真实模型调用的 OTA Agent 运行时。

Agent 按 Observe -> Think -> Act 循环运行，并在 Act 阶段通过统一
LLMFactory 调用 models.yaml 中注册的模型。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import (
    AuditEvent,
    LLMRequestEvent,
    LLMResponseEvent,
    PermissionRequestEvent,
    PermissionResultEvent,
    ReasoningDeltaEvent,
    ReasoningFinishEvent,
    ReasoningStartEvent,
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
from bamboo.llms import LLMContextLengthError, LLMError, LLMRequest, LLMRequestError, LLMResponse, LLMToolCall
from bamboo.prompts import render_prompt_sections
from bamboo.runtime.prompt import AgentPrompt
from bamboo.runtime.runtime_context import RuntimeContext
from bamboo.runtime.state_machine import AgentState, AgentStateMachine
from bamboo.runtime.tool_result_budget import ToolResultBudgeter
from bamboo.security import PermissionDecision, PermissionRequest, PermissionResult, ToolAuditRecord


@dataclass(slots=True)
class AgentRecoveryPolicy:
    """配置 Agent 单次循环错误后的恢复策略。"""

    max_iterations: int = 100
    max_recoverable_errors: int = 5
    continue_after_error: bool = True


@dataclass(slots=True)
class AgentRunState:
    """记录一次 Agent 运行中的循环次数和可恢复错误。"""

    iteration: int = 0
    compaction_count: int = 0
    recoverable_errors: list[str] = field(default_factory=list)
    full_system_prompt_saved: bool = False


@dataclass(slots=True)
class _DeferredSessionMessage:
    role: str
    content: str
    agent_name: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class _ToolCallOutcome:
    messages: list[_DeferredSessionMessage] = field(default_factory=list)
    events: list[ToolResultEvent | ToolErrorEvent] = field(default_factory=list)
    compact_tool_results: bool = False


class AgentRuntimeError(RuntimeError):
    """表示 Agent 已耗尽恢复预算。"""


def _serialize_llm_messages_for_trace(request: LLMRequest) -> list[dict[str, Any]]:
    """Serialize the exact LLM messages used for a provider request."""
    rows: list[dict[str, Any]] = []
    for index, message in enumerate(request.messages):
        rows.append(
            {
                "index": index,
                "role": message.role,
                "content": message.content,
                "images": [
                    {"source": image.source, "media_type": image.media_type, "detail": image.detail}
                    for image in message.images
                ],
                "tool_calls": [
                    {"id": tool_call.id, "name": tool_call.name, "arguments": dict(tool_call.arguments)}
                    for tool_call in message.tool_calls
                ],
                "tool_call_id": message.tool_call_id,
                "tool_name": message.tool_name,
            }
        )
    return rows


def _render_llm_request_for_trace(request: LLMRequest) -> str:
    """Render the full prompt sent to an LLM in a log-friendly format."""
    sections = ["# System Prompt", request.system_prompt or "(empty)", "# Messages"]
    if not request.messages:
        sections.append("(none)")
    for index, message in enumerate(request.messages, start=1):
        chunks = [f"## Message {index} · {message.role}", message.content or ""]
        if message.images:
            chunks.append(
                "Images:\n"
                + "\n".join(
                    f"- {image.source} media_type={image.media_type or 'auto'} detail={image.detail}"
                    for image in message.images
                )
            )
        if message.tool_calls:
            chunks.append(
                "Tool Calls:\n"
                + "\n".join(
                    f"- {tool_call.name}({tool_call.arguments}) id={tool_call.id}"
                    for tool_call in message.tool_calls
                )
            )
        if message.tool_call_id:
            chunks.append(f"tool_call_id: {message.tool_call_id}")
        sections.append("\n\n".join(chunks).strip())
    if request.tools:
        sections.extend(["# Tools", "\n".join(f"- {tool.get('name', '')}" for tool in request.tools)])
    return "\n\n".join(sections)


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
        self.llm_router = runtime_context.llm_router
        self.main_route = runtime_context.main_route
        self.compaction_route = runtime_context.compaction_route
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
        self.tool_call_timeout_seconds = runtime_context.tool_call_timeout_seconds
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
        observation = self.prompt_builder.build(
            task.session,
            error_history=self.run_state.recoverable_errors,
        )
        self._maybe_persist_full_system_prompt(task, observation)
        return observation

    def _maybe_persist_full_system_prompt(self, task: Task, observation: AgentPrompt) -> None:
        """首次构建完整 prompt 时覆盖 system_prompt.md，之后不再改写。"""
        if self.run_state.full_system_prompt_saved:
            return
        memory_store = getattr(task.session, "memory_store", None)
        if memory_store is None:
            return
        if observation.prompt_sections:
            full_prompt = render_prompt_sections(observation.prompt_sections)
        else:
            full_prompt = observation.system_prompt
        memory_store.save_full_system_prompt(full_prompt)
        self.run_state.full_system_prompt_saved = True

    async def _think(self, task: Task, observation: AgentPrompt) -> LLMResponse:
        """调用主模型分析当前观察结果，并返回可供 Act 执行的模型决策。"""
        if task.metadata.pop("inject_agent_error_once", "") == "thinking":
            raise RuntimeError("Injected mock thinking error")
        request = observation.to_llm_request()
        try:
            return await self._complete_main_with_fallback(task, request)
        except LLMContextLengthError as exc:
            return await self._reactive_compact_and_retry(task, exc)

    async def _complete_main_with_fallback(self, task: Task, request: LLMRequest) -> LLMResponse:
        """调用当前主模型；遇到可 fallback 错误时只切换一次并重试。"""
        try:
            return await self._call_llm_client(task, request, role="main")
        except LLMError as exc:
            if not self.llm_router.can_fallback(self.main_route, exc):
                raise
            fallback_from = self.main_route.active_model_name
            fallback_to = self.llm_router.activate_fallback(self.main_route)
            self.model_name = fallback_to
            self.model_config = self.llm_router.config_for(self.main_route)
            self.prompt_builder.set_model_config(self.model_config)
            self.llm_client = self.llm_router.client_for(self.main_route)
            task.metadata["fallback_used"] = "true"
            task.metadata["fallback_from"] = fallback_from
            task.metadata["fallback_to"] = fallback_to
            task.metadata["fallback_error_type"] = exc.error_type
            task.metadata["fallback_error"] = str(exc)
            await self.event_bus.emit(
                AuditEvent(
                    session_id=task.session_id,
                    task_id=task.task_id,
                    action="llm_fallback_activated",
                    result=f"{fallback_from} -> {fallback_to} ({exc.error_type})",
                    approved=True,
                )
            )
            return await self._call_llm_client(task, request, role="main")

    async def _call_llm_client(self, task: Task, request: LLMRequest, *, role: str) -> LLMResponse:
        """调用模型并发布脱敏 LLM trace 事件。"""
        self._validate_image_request(request)
        request_event = LLMRequestEvent(
            session_id=task.session_id,
            task_id=task.task_id,
            role=role,
            model_name=self.model_name,
            provider=self.model_config.provider,
            prompt_profile=self.model_config.prompt_profile,
            message_count=len(request.messages),
            tool_count=len(request.tools),
            system_prompt_chars=len(request.system_prompt),
            input_chars=len(request.system_prompt) + sum(len(message.content) for message in request.messages),
            system_prompt=request.system_prompt,
            messages=_serialize_llm_messages_for_trace(request),
            full_prompt=_render_llm_request_for_trace(request),
        )
        await self.event_bus.emit(request_event)
        try:
            response = await self.llm_client.complete(request)
        except LLMError as exc:
            await self.event_bus.emit(
                LLMResponseEvent(
                    session_id=task.session_id,
                    task_id=task.task_id,
                    parent_event_id=request_event.event_id,
                    role=role,
                    model_name=self.model_name,
                    provider=self.model_config.provider,
                    success=False,
                    error_type=exc.error_type,
                    error=str(exc)[:500],
                )
            )
            raise
        except Exception as exc:
            await self.event_bus.emit(
                LLMResponseEvent(
                    session_id=task.session_id,
                    task_id=task.task_id,
                    parent_event_id=request_event.event_id,
                    role=role,
                    model_name=self.model_name,
                    provider=self.model_config.provider,
                    success=False,
                    error_type=type(exc).__name__,
                    error=str(exc)[:500],
                )
            )
            raise
        await self.event_bus.emit(
            LLMResponseEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                parent_event_id=request_event.event_id,
                role=role,
                model_name=self.model_name,
                provider=response.provider,
                response_model=response.model,
                finish_reason=response.finish_reason,
                output_chars=len(response.content),
                tool_call_count=len(response.tool_calls),
                usage=dict(response.usage),
                success=True,
            )
        )
        return response

    def _validate_image_request(self, request: LLMRequest) -> None:
        """Reject image requests for text-only model registrations."""
        image_count = sum(len(message.images) for message in request.messages)
        if image_count == 0:
            return
        if self.model_config.model_type == "vision" and self.model_config.capabilities.vision:
            return
        raise LLMRequestError(
            (
                f"Model '{self.model_name}' is not configured for image input. "
                "Set model_type: vision and capabilities.vision: true in models.yaml."
            ),
            error_type="request",
            retryable=False,
        )

    async def _reactive_compact_and_retry(self, task: Task, exc: LLMContextLengthError) -> LLMResponse:
        """模型明确返回上下文过长时，强制压缩后重建 prompt 并重试一次。"""
        before_prompt = self._observe(task)
        before_budget = self.context_compactor.evaluate(before_prompt)
        await self._transition(
            task,
            AgentState.COMPACTING,
            f"reactive compact after context_length error: {exc}",
        )
        compacted = await self.context_compactor.compact(task.session, force=True)
        await self._transition(task, AgentState.OBSERVING, "rebuild context after reactive compaction")
        if not compacted:
            task.metadata["reactive_compaction_failed"] = str(exc)
            raise exc

        rebuilt_prompt = self._observe(task)
        rebuilt_budget = self.context_compactor.evaluate(rebuilt_prompt)
        self.run_state.compaction_count += 1
        task.metadata["context_compaction_count"] = str(self.run_state.compaction_count)
        task.metadata["context_compaction_model"] = self.compaction_model_name
        task.metadata["reactive_compaction_count"] = str(
            int(task.metadata.get("reactive_compaction_count", "0")) + 1
        )
        await self.event_bus.emit(
            SessionCompactEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                before_token_count=before_budget.input_tokens,
                after_token_count=rebuilt_budget.input_tokens,
                reason="reactive",
            )
        )
        await self._transition(task, AgentState.THINKING, "retry model after reactive compaction")
        return await self._complete_main_with_fallback(task, rebuilt_prompt.to_llm_request())

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
                    reason="preemptive",
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
            message = task.session.add_message(
                "assistant",
                decision.content,
                agent_name=f"llm:{self.model_name}",
                metadata={"reasoning_content": decision.reasoning_content} if decision.reasoning_content else None,
                tool_calls=list(decision.tool_calls),
            )
            await self._emit_reasoning(task, message.message_id, decision.reasoning_content)
            await self._transition(task, AgentState.TOOL_CALLING, "execute model tool calls")
            if self._can_parallelize_tool_calls(task, decision.tool_calls):
                await self._execute_tool_calls_parallel(task, decision.tool_calls)
            else:
                for tool_call in decision.tool_calls:
                    await self._execute_tool_call(task, tool_call)
            current_count = int(task.metadata.get("tool_call_count", "0"))
            task.metadata["tool_call_count"] = str(current_count + len(decision.tool_calls))
            return False

        content = decision.content

        message = task.session.add_message(
            "assistant",
            content,
            agent_name=f"llm:{self.model_name}",
            metadata={"reasoning_content": decision.reasoning_content} if decision.reasoning_content else None,
        )
        await self._emit_reasoning(task, message.message_id, decision.reasoning_content)
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

    async def _emit_reasoning(self, task: Task, message_id: str, content: str) -> None:
        """Emit reasoning as a separate stream so renderers can fold it independently."""
        if not content:
            return
        await self.event_bus.emit(
            ReasoningStartEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                message_id=message_id,
            )
        )
        await self.event_bus.emit(
            ReasoningDeltaEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                delta=content,
            )
        )
        await self.event_bus.emit(
            ReasoningFinishEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                message_id=message_id,
                content=content,
            )
        )

    async def _execute_tool_calls_parallel(self, task: Task, tool_calls: list[LLMToolCall]) -> None:
        """Execute same-turn read-only tool calls concurrently and write results in model order."""
        outcomes = await asyncio.gather(
            *(self._run_tool_call(task, tool_call) for tool_call in tool_calls),
        )
        for outcome in outcomes:
            await self._flush_tool_call_outcome(task, outcome)

    async def _execute_tool_call(self, task: Task, tool_call: LLMToolCall) -> None:
        """执行一条模型 Tool Call，并把结果或错误写回 Session 与 EventBus。"""
        outcome = await self._run_tool_call(task, tool_call)
        await self._flush_tool_call_outcome(task, outcome)

    async def _run_tool_call(self, task: Task, tool_call: LLMToolCall) -> _ToolCallOutcome:
        """Execute one tool call and return deferred session/event writes."""
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
            return self._tool_error_outcome(task, tool_call, f"Tool is unavailable: {tool_call.name}")
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
            return self._tool_error_outcome(task, tool_call, f"Tool call denied: {permission.reason}")

        started_at = time.perf_counter()
        timeout_seconds = self._tool_call_timeout_seconds(tool)
        try:
            result = await asyncio.wait_for(
                tool.execute(**tool_call.arguments),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            error = f"Tool call timed out after {timeout_seconds:g}s"
            await self._audit_tool_call(
                task,
                tool_call,
                permission,
                success=False,
                error=error,
                duration_ms=duration_ms,
            )
            return self._tool_error_outcome(task, tool_call, error)
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
            return self._tool_error_outcome(task, tool_call, f"Tool execution raised: {exc}")

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
                sandbox=result.metadata.get("sandbox", {}) if result.metadata else {},
            )
            return self._tool_error_outcome(task, tool_call, error)

        await self._audit_tool_call(
            task,
            tool_call,
            permission,
            success=True,
            duration_ms=duration_ms,
            output_preview=result.content,
            sandbox=result.metadata.get("sandbox", {}) if result.metadata else {},
        )
        budgeted_result = self.tool_result_budgeter.prepare_for_session(result.content)
        return _ToolCallOutcome(
            messages=[
                _DeferredSessionMessage(
                    role="tool",
                    content=budgeted_result.context_content,
                    agent_name=tool_call.name,
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    metadata={
                        "tool_result_budget": budgeted_result.metadata,
                    },
                )
            ],
            events=[
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
            ],
            compact_tool_results=True,
        )

    def _tool_call_timeout_seconds(self, tool: Tool) -> float:
        override = tool.timeout_override_seconds()
        if override is not None and override > 0:
            return float(override)
        return self.tool_call_timeout_seconds

    async def _flush_tool_call_outcome(self, task: Task, outcome: _ToolCallOutcome) -> None:
        """Write deferred tool messages and events in a stable order."""
        for message in outcome.messages:
            task.session.add_message(
                message.role,
                message.content,
                agent_name=message.agent_name,
                tool_call_id=message.tool_call_id,
                tool_name=message.tool_name,
                metadata=message.metadata,
            )
        if outcome.compact_tool_results:
            self.tool_result_budgeter.compact_old_tool_results(task.session)
        for event in outcome.events:
            await self.event_bus.emit(event)

    def _tool_error_outcome(self, task: Task, tool_call: LLMToolCall, error: str) -> _ToolCallOutcome:
        """Build deferred writes for a tool error."""
        return _ToolCallOutcome(
            messages=[
                _DeferredSessionMessage(
                    role="tool",
                    content=f"[tool-error]\n{error}",
                    agent_name=tool_call.name,
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                )
            ],
            events=[
                ToolErrorEvent(
                    session_id=task.session_id,
                    task_id=task.task_id,
                    tool_name=tool_call.name,
                    tool_call_id=tool_call.id,
                    error=error,
                )
            ],
        )

    def _can_parallelize_tool_calls(self, task: Task, tool_calls: list[LLMToolCall]) -> bool:
        """Return True only when every same-turn tool call has effective read risk."""
        if len(tool_calls) < 2:
            return False
        return all(self._assess_tool_call_risk(task, tool_call).risk_level == "read" for tool_call in tool_calls)

    def _assess_tool_call_risk(self, task: Task, tool_call: LLMToolCall) -> PermissionResult:
        """Assess effective risk with the same request data used by authorization."""
        request = self._build_permission_request(task, tool_call)
        if self.permission_policy is None:
            return PermissionResult(PermissionDecision.ALLOW, request.risk_level, "permission policy disabled")
        return self.permission_policy.assess_risk(request)

    def _build_permission_request(self, task: Task, tool_call: LLMToolCall) -> PermissionRequest:
        """Build a permission request for policy assessment and authorization."""
        metadata = self.tool_registry.get_metadata(tool_call.name)
        return PermissionRequest(
            session_id=task.session_id,
            task_id=task.task_id,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            arguments=dict(tool_call.arguments),
            risk_level=metadata.risk_level if metadata is not None else "read",
            source=metadata.source if metadata is not None else "unknown",
        )

    async def _authorize_tool_call(self, task: Task, tool_call: LLMToolCall) -> PermissionResult:
        """Run permission policy and emit permission lifecycle events."""
        request = self._build_permission_request(task, tool_call)
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
        sandbox: dict | None = None,
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
            sandbox=dict(sandbox or {}),
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
