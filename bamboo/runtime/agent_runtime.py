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
    SessionStatusChangeEvent,
    TextDeltaEvent,
    TextFinishEvent,
    TextStartEvent,
)
from bamboo.llms import LLMFactory
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
        state_machine: AgentStateMachine | None = None,
        prompt_builder: AgentPromptBuilder | None = None,
        recovery_policy: AgentRecoveryPolicy | None = None,
    ) -> None:
        """初始化 Agent 运行依赖，并固定当前 Agent 使用的模型客户端。"""
        self.event_bus = event_bus
        self.state_machine = state_machine or AgentStateMachine()
        self.prompt_builder = prompt_builder or AgentPromptBuilder()
        self.recovery_policy = recovery_policy or AgentRecoveryPolicy()
        self.llm_factory = llm_factory
        self.model_name = model_name
        self.llm_client = self.llm_factory.get_client(self.model_name)
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

        await self._transition(task, AgentState.THINKING, "prepare model request")
        thought = self._think(task, observation)

        await self._transition(task, AgentState.ACTING, "call model and write answer")
        await self._act(task, thought)

        await self._transition(task, AgentState.COMPLETED, "agent completed")
        return task

    def _observe(self, task: Task) -> AgentPrompt:
        """收集本轮 Agent 需要观察的上下文。"""
        return self.prompt_builder.build(
            task.session,
            error_history=self.run_state.recoverable_errors,
        )

    def _think(self, task: Task, observation: AgentPrompt) -> AgentPrompt:
        """检查本轮 prompt，并把结构化请求材料交给 Act 阶段。"""
        if task.metadata.pop("inject_agent_error_once", "") == "thinking":
            raise RuntimeError("Injected mock thinking error")
        return observation

    async def _act(self, task: Task, prompt: AgentPrompt) -> None:
        """通过统一 LLMFactory 调用模型，并发布返回文本事件。"""
        if task.metadata.pop("inject_agent_error_once", "") == "acting":
            raise RuntimeError("Injected mock acting error")

        response = await self.llm_client.complete(prompt.to_llm_request())
        content = response.content

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
        task.metadata["llm_model"] = response.model
        task.metadata["llm_provider"] = response.provider

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
