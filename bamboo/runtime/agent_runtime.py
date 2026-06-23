"""带可恢复错误处理和真实模型调用的 OTA Agent 运行时。

Agent 按 Observe -> Think -> Act 循环运行，并在 Act 阶段通过统一
LLMFactory 调用 models.yaml 中注册的模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import (
    AuditEvent,
    SessionCompactEvent,
    SessionStatusChangeEvent,
    TextDeltaEvent,
    TextFinishEvent,
    TextStartEvent,
)
from bamboo.llms import LLMFactory, LLMResponse
from bamboo.runtime.context_compactor import ContextBudgetPolicy, ContextCompactor, TokenCounter
from bamboo.runtime.prompt import AgentPrompt, AgentPromptBuilder
from bamboo.runtime.state_machine import AgentState, AgentStateMachine


@dataclass(slots=True)
class AgentRecoveryPolicy:
    """配置 Agent 单次循环错误后的恢复策略。"""

    max_iterations: int = 3
    max_recoverable_errors: int = 2
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
        event_bus: EventBus,
        llm_factory: LLMFactory,
        model_name: str,
        compaction_model_name: str | None = None,
        state_machine: AgentStateMachine | None = None,
        prompt_builder: AgentPromptBuilder | None = None,
        recovery_policy: AgentRecoveryPolicy | None = None,
        compaction_policy: ContextBudgetPolicy | None = None,
        token_counter: TokenCounter | None = None,
        context_compactor: ContextCompactor | None = None,
    ) -> None:
        """初始化 Agent 运行依赖，并固定当前 Agent 使用的模型客户端。"""
        self.event_bus = event_bus
        self.state_machine = state_machine or AgentStateMachine()
        self.prompt_builder = prompt_builder or AgentPromptBuilder()
        self.recovery_policy = recovery_policy or AgentRecoveryPolicy()
        self.llm_factory = llm_factory
        self.model_name = model_name
        self.compaction_model_name = compaction_model_name or model_name
        self.model_config = self.llm_factory.get_model_config(self.model_name)
        self.llm_client = self.llm_factory.get_client(self.model_name)
        self.compaction_llm_client = self.llm_factory.get_client(self.compaction_model_name)
        self.context_compactor = context_compactor or ContextCompactor(
            llm_client=self.compaction_llm_client,
            # 是否压缩仍按主 Agent 模型的上下文窗口判断。
            model_config=self.model_config,
            token_counter=token_counter,
            policy=compaction_policy,
        )
        self.run_state = AgentRunState()

    async def run(self, task: Task) -> Task:
        """执行 OTA 循环，直到完成或恢复预算耗尽。"""
        while self.run_state.iteration < self.recovery_policy.max_iterations:
            self.run_state.iteration += 1
            try:
                return await self._run_one_cycle(task)
            except Exception as exc:
                # 单轮失败不立刻让任务失败，先尝试把错误写入上下文并继续下一轮。
                if not await self._recover(task, exc):
                    await self._transition(task, AgentState.FAILED, "agent recovery exhausted")
                    raise AgentRuntimeError(str(exc)) from exc

        await self._transition(task, AgentState.FAILED, "agent max iterations exhausted")
        raise AgentRuntimeError("Agent max iterations exhausted")

    async def _run_one_cycle(self, task: Task) -> Task:
        """执行一轮 Observe -> Think -> Act。"""
        await self._transition(task, AgentState.OBSERVING, "collect context")
        observation = self._observe(task)
        observation = await self._compact_context_if_needed(task, observation)

        await self._transition(task, AgentState.THINKING, "call model and produce decision")
        thought = await self._think(task, observation)

        await self._transition(task, AgentState.ACTING, "apply model decision")
        await self._act(task, thought)

        await self._transition(task, AgentState.COMPLETED, "agent completed")
        return task

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
        return await self.llm_client.complete(observation.to_llm_request())

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

    async def _act(self, task: Task, decision: LLMResponse) -> None:
        """应用 Think 阶段产生的模型决策，并发布文本结果事件。"""
        if task.metadata.pop("inject_agent_error_once", "") == "acting":
            raise RuntimeError("Injected mock acting error")

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
