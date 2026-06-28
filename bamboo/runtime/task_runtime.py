"""Bamboo 任务运行时编排层。

TaskRuntime 是一次任务执行的总控：创建任务、保存状态、发布事件、
启动 AgentRuntime，并在 Agent 整体失败时尝试任务级恢复。
"""

# 延迟解析类型注解，避免运行时立即解析 `TaskFactory | None` 等类型表达式。
from __future__ import annotations

# Callable 用于描述可注入的 AgentRuntime 工厂函数类型。
from collections.abc import Callable

# dataclass 用于声明轻量配置对象，field 用于给列表字段创建独立默认值，replace 用于派生新运行参数。
from dataclasses import dataclass, field, replace
from uuid import uuid4

# EventBus 是运行时事件总线，get_event_bus 返回进程内默认事件总线实例。
from bamboo.factory.event_bus import EventBus, get_event_bus

# Task 是任务数据对象，TaskFactory 负责从输入参数创建 Task / Session / Context。
from bamboo.factory.task_factory import Task, TaskFactory

# 这些事件会被 TaskRuntime 发布到 EventBus，供 CLI、Web UI 或日志订阅者消费。
from bamboo.helpers.constant import AuditEvent, StepFinishEvent, StepStartEvent, TaskCreateEvent, TaskStatusChangeEvent

# get_logger 返回项目统一配置过的日志对象。
from bamboo.helpers.logging import get_logger

# RunParams 是 CLI 或调试入口整理后的运行参数。
from bamboo.helpers.requests_params import RunParams

# LLMFactory 在 TaskRuntime 初始化时加载模型配置，并为本次执行提供模型路由。
from bamboo.llms import LLMFactory

# AgentRuntime 执行 Agent 的 OTA 循环，AgentRuntimeError 表示 Agent 层运行失败。
from bamboo.runtime.agent_runtime import AgentRuntime, AgentRuntimeError
from bamboo.runtime.runtime_context import RuntimeContextBuilder

# InMemoryTaskStore 保存任务生命周期快照，当前实现是内存级存储。
from bamboo.runtime.store import InMemoryTaskStore


@dataclass(slots=True)
class TaskRecoveryPolicy:
    """配置 Agent 整体失败后 TaskRuntime 如何继续。"""

    # AgentRuntime 整体失败后，TaskRuntime 最多允许重新创建并执行 Agent 的次数。
    max_agent_attempts: int = 2
    # 是否允许 Agent 抛错后继续下一次任务级尝试；关闭后第一次错误就会失败任务。
    continue_after_agent_error: bool = True


@dataclass(slots=True)
class TaskRunState:
    """记录任务级重试次数和可恢复错误。"""

    # 当前已经执行过的 Agent 尝试次数，从 0 开始，每进入一次循环加 1。
    agent_attempt: int = 0
    # 记录每次可恢复 Agent 错误的文本，方便后续追踪和写入 prompt 上下文。
    recoverable_errors: list[str] = field(default_factory=list)


class TaskRuntime:
    """编排一个 Task 的完整生命周期。"""

    def __init__(
        self,
        *,
        task_factory: TaskFactory | None = None,
        event_bus: EventBus | None = None,
        task_store: InMemoryTaskStore | None = None,
        recovery_policy: TaskRecoveryPolicy | None = None,
        agent_factory: Callable[[EventBus], AgentRuntime] | None = None,
        llm_factory: LLMFactory | None = None,
        runtime_context_builder: RuntimeContextBuilder | None = None,
    ) -> None:
        """初始化运行时依赖。"""
        self.task_factory = task_factory or TaskFactory()
        self.event_bus = event_bus or get_event_bus()
        # task_store 负责保存任务状态快照；未注入时使用内存存储。
        self.task_store = task_store or InMemoryTaskStore()
        # recovery_policy 控制 Agent 整体失败后的重试次数和是否继续执行。
        self.recovery_policy = recovery_policy or TaskRecoveryPolicy()
        # agent_factory 允许测试或未来真实 Agent 注入替代实现；为空时由运行时创建标准 Agent。
        self.agent_factory = agent_factory
        # TaskRuntime 初始化时加载一次模型配置；本次执行创建的所有 Agent 复用该工厂。
        self.llm_factory = llm_factory or LLMFactory.from_bamboo_config(self.task_factory.config)
        # runtime_context_builder 集中创建 Agent 执行依赖；为空时使用默认构建器。
        self.runtime_context_builder = runtime_context_builder or RuntimeContextBuilder(
            event_bus=self.event_bus,
            llm_factory=self.llm_factory,
        )
        # _log 是 TaskRuntime 专用日志器，用于记录任务级异常。
        self._log = get_logger("TaskRuntime")

    async def run(self, run_params: RunParams) -> Task:
        """运行一个任务，并在 Agent 整体失败时按策略重试。"""
        # task 是当前要执行的任务对象，内部包含 session、context、用户输入和状态。
        task = self.create_task(run_params)
        return await self.run_existing_task(task)

    def create_task(self, run_params: RunParams) -> Task:
        """根据入口参数创建一个全新的 Task 和 Session。"""
        # TaskFactory 负责把标准化输入转换为 Task，并创建本次会话的初始 Session。
        return self.task_factory.create(run_params)

    def create_followup_task(self, previous_task: Task, message: str) -> Task:
        """基于已有 Session 创建下一轮用户输入对应的新 Task。"""
        # task_id 每一轮都独立，便于事件、日志和任务状态按轮次追踪。
        task_id = str(uuid4())
        # run_params 保存本轮输入，同时沿用上一轮的 session_id 和其他入口参数。
        run_params = replace(
            previous_task.run_params,
            message=message,
            task_id=task_id,
            session_id=previous_task.session_id,
        )
        # 同一个交互会话内复用 Session，并把本轮用户消息追加到上下文末尾。
        previous_task.session.add_message("user", message)
        # 返回一个新的 Task 对象，避免在 CLI 层手动重置旧 Task 的运行状态字段。
        return Task(
            platform=previous_task.platform,
            session_id=previous_task.session_id,
            task_id=task_id,
            user_query=message,
            session=previous_task.session,
            config=previous_task.config,
            run_params=run_params,
            memory_dir=previous_task.memory_dir,
        )

    async def run_existing_task(self, task: Task) -> Task:
        """运行已经创建好的 Task，供交互式会话复用同一个 Session。"""
        # state 保存本次 TaskRuntime 执行期间的尝试次数和可恢复错误。
        state = TaskRunState()
        # 任务创建后先落入 store，再发事件，保证外部订阅者看到的是已存在任务。
        self.task_store.save_created(task)
        # 通知订阅者任务已经创建，例如 CLI 可以据此打印 task created。
        await self._emit_task_created(task)
        # 将任务从 created 推进到 running，并发布状态变化事件。
        await self._transition_task(task, "created", "running")
        # 当前框架把整个 Agent OTA 循环视为一个步骤，这里发布步骤开始事件。
        await self._emit_step_started(task)

        # 在恢复预算内重复尝试 Agent；每次失败后由 _recover_agent_failure 判断是否继续。
        while state.agent_attempt < self.recovery_policy.max_agent_attempts:
            # agent_attempt 记录当前是第几次 Agent 尝试，第一次进入循环后为 1。
            state.agent_attempt += 1
            try:
                # 每次任务级重试都创建新的 AgentRuntime，避免复用已损坏的状态机。
                agent = self._create_agent(task)
                # 执行 Agent OTA 循环；成功后返回带有结果和状态更新的 task。
                task = await agent.run(task)
                # Agent 成功完成后，将任务状态标记为 completed。
                await self._transition_task(task, "running", "completed")
                # 发布步骤完成事件，summary 会被 CLI 或 UI 展示。
                await self._emit_step_finished(task, "Bamboo task completed.")
                # 任务成功结束，返回最终 Task 给调用方。
                return task
            except Exception as exc:
                # exc 是本次 Agent 尝试抛出的异常，交给任务级恢复逻辑处理。
                if not await self._recover_agent_failure(task, state, exc):
                    # 如果恢复策略不允许继续，或重试次数已耗尽，则把任务标记为失败。
                    await self._fail_task(task, exc)
                    # 继续向上抛出异常，让外层入口知道本次运行失败。
                    raise

        # 理论上循环耗尽后会走到这里，构造统一的 AgentRuntimeError 表示重试预算耗尽。
        error = AgentRuntimeError("TaskRuntime exhausted agent attempts")
        # 把耗尽重试预算的任务保存为 failed，并发布步骤失败事件。
        await self._fail_task(task, error)
        # 抛出最终错误，保持运行入口可以感知失败。
        raise error

    async def _recover_agent_failure(self, task: Task, state: TaskRunState, exc: Exception) -> bool:
        """记录 Agent 整体失败，并判断任务是否还能继续。"""
        # error 是带尝试次数的错误摘要，方便排查是哪一轮 Agent 出错。
        error = f"agent_attempt={state.agent_attempt}: {exc}"
        # recoverable_errors 保存历史可恢复错误，目前用于记录和未来扩展。
        state.recoverable_errors.append(error)
        # task.error 保存最近一次任务级错误，供 store、日志或 UI 读取。
        task.error = error
        # metadata 中记录最后一次任务恢复错误，避免污染固定字段。
        task.metadata["last_task_recovery_error"] = error
        # 把恢复信息写回 session，下一次 Agent 尝试可在 prompt 中看到失败原因。
        task.session.add_message("system", f"[recoverable-task-error]\n{error}", agent_name="runtime")
        # 保存错误快照，即使后续恢复成功，也能追踪曾经发生过的 Agent 失败。
        self.task_store.save_error(task, error)

        # 发布审计事件，说明 TaskRuntime 捕获了 Agent 错误并进入恢复判断。
        await self.event_bus.emit(
            AuditEvent(
                # session_id 标识本次对话会话。
                session_id=task.session_id,
                # task_id 标识当前任务。
                task_id=task.task_id,
                # action 是审计动作名称，便于订阅者按动作过滤。
                action="task_agent_error_recovered",
                # result 保存错误文本。
                result=error,
                # approved 表示该恢复动作由运行时策略允许。
                approved=True,
            )
        )

        # should_continue 表示任务级恢复策略是否允许再创建一个新的 AgentRuntime 继续执行。
        should_continue = (
            # continue_after_agent_error 为 False 时，任何 Agent 错误都会立即终止任务。
            self.recovery_policy.continue_after_agent_error
            # 只有当前尝试次数小于最大次数，才还有下一次 Agent 尝试预算。
            and state.agent_attempt < self.recovery_policy.max_agent_attempts
        )
        if should_continue:
            # 任务仍保持 running，只发布一次 running -> running，告诉外部发生了恢复重试。
            await self._transition_task(task, "running", "running")
            # 返回 True 表示 TaskRuntime 可以回到 while 循环继续执行。
            return True
        # 返回 False 表示恢复预算耗尽或策略禁止继续，调用方应失败任务。
        return False

    async def _fail_task(self, task: Task, exc: Exception) -> None:
        """恢复预算耗尽后，将任务标记为失败。"""
        # task.error 保存最终失败原因。
        task.error = str(exc)
        # 记录完整异常日志，exception 会带上当前异常栈。
        self._log.exception(
            "task failed task_id={task_id} session_id={session_id}",
            # task_id 用于在日志中定位失败任务。
            task_id=task.task_id,
            # session_id 用于在日志中定位失败会话。
            session_id=task.session_id,
        )
        # 将任务当前状态推进到 failed，并发布状态变化事件。
        await self._transition_task(task, task.status, "failed")
        # 保存失败快照，便于后续查询失败原因。
        self.task_store.save_error(task, task.error)
        # 发布步骤完成事件，但 summary 中明确说明任务失败。
        await self._emit_step_finished(task, f"Bamboo task failed: {task.error}")

    def _create_agent(self, task: Task) -> AgentRuntime:
        """使用任务配置和模型名为本次尝试初始化 AgentRuntime。"""
        # 注入自定义工厂时，由调用方负责构造完整 AgentRuntime。
        if self.agent_factory is not None:
            return self.agent_factory(self.event_bus)
        # 默认 Agent 接收 RuntimeContextBuilder 已经装配好的完整运行上下文。
        return AgentRuntime(runtime_context=self.runtime_context_builder.build(task))

    async def _transition_task(self, task: Task, from_status: str, to_status: str) -> None:
        """更新任务状态、持久化快照并发布状态事件。"""
        # task.status 是任务当前状态；这里写入新的目标状态。
        task.status = to_status  # type: ignore[assignment]
        # 将状态变化保存到任务存储。
        self.task_store.save_status(task, to_status)
        # 发布任务状态变化事件，外部订阅者可以据此更新 UI 或打印日志。
        await self.event_bus.emit(
            TaskStatusChangeEvent(
                # session_id 标识状态变化所属会话。
                session_id=task.session_id,
                # task_id 标识状态变化所属任务。
                task_id=task.task_id,
                # from_status 是状态变化前的状态。
                from_status=from_status,
                # to_status 是状态变化后的状态。
                to_status=to_status,
            )
        )

    async def _emit_task_created(self, task: Task) -> None:
        """发布任务创建事件。"""
        # TaskCreateEvent 告诉外部系统一个新任务已经创建。
        await self.event_bus.emit(
            TaskCreateEvent(
                # session_id 关联任务所属会话。
                session_id=task.session_id,
                # task_id 是新任务的唯一标识。
                task_id=task.task_id,
                # title 当前使用用户输入作为任务标题；为空时退化为空字符串。
                title=task.user_query or "",
            )
        )

    async def _emit_step_started(self, task: Task) -> None:
        """发布 Agent 步骤开始事件。"""
        # StepStartEvent 表示一个可展示的执行步骤开始。
        await self.event_bus.emit(
            StepStartEvent(
                # session_id 标识步骤所属会话。
                session_id=task.session_id,
                # task_id 标识步骤所属任务。
                task_id=task.task_id,
                # step_id 是稳定步骤标识；当前整个 OTA Agent 统一叫 ota-agent。
                step_id="ota-agent",
                # step_index 是步骤顺序；当前只有一个步骤，所以固定为 0。
                step_index=0,
            )
        )

    async def _emit_step_finished(self, task: Task, summary: str) -> None:
        """发布 Agent 步骤完成事件。"""
        # StepFinishEvent 表示一个可展示的执行步骤结束。
        await self.event_bus.emit(
            StepFinishEvent(
                # session_id 标识步骤所属会话。
                session_id=task.session_id,
                # task_id 标识步骤所属任务。
                task_id=task.task_id,
                # step_id 必须和开始事件一致，方便订阅者配对。
                step_id="ota-agent",
                # step_index 必须和开始事件一致，表示当前步骤在流程中的位置。
                step_index=0,
                # summary 是步骤结束摘要，成功和失败都会通过它传递给外部。
                summary=summary,
            )
        )
