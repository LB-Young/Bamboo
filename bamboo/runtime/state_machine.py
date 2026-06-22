"""mock OTA Agent 的状态机。

状态机只负责校验状态迁移是否合法，不执行业务动作，也不保存任务结果。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgentState(StrEnum):
    """定义 Observe-Think-Act 循环中的状态。"""

    CREATED = "created"
    OBSERVING = "observing"
    THINKING = "thinking"
    ACTING = "acting"
    TOOL_CALLING = "tool_calling"
    COMPACTING = "compacting"
    RECOVERING = "recovering"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = {AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED}


@dataclass(slots=True)
class AgentStateMachine:
    """校验并记录一次 Agent 运行中的状态迁移。"""

    state: AgentState = AgentState.CREATED

    def transition(self, next_state: AgentState) -> tuple[AgentState, AgentState]:
        """在迁移合法时进入下一个状态。"""
        current_state = self.state
        if not self.can_transition(next_state):
            raise ValueError(f"Invalid agent state transition: {current_state.value} -> {next_state.value}")
        self.state = next_state
        return current_state, next_state

    def can_transition(self, next_state: AgentState) -> bool:
        """判断当前状态是否可以迁移到目标状态。"""
        if self.state in TERMINAL_STATES:
            return False
        allowed: dict[AgentState, set[AgentState]] = {
            AgentState.CREATED: {AgentState.OBSERVING, AgentState.FAILED, AgentState.CANCELLED},
            AgentState.OBSERVING: {
                AgentState.THINKING,
                AgentState.COMPACTING,
                AgentState.RECOVERING,
                AgentState.WAITING,
                AgentState.FAILED,
                AgentState.CANCELLED,
            },
            AgentState.THINKING: {AgentState.ACTING, AgentState.RECOVERING, AgentState.FAILED, AgentState.CANCELLED},
            AgentState.ACTING: {
                AgentState.OBSERVING,
                AgentState.TOOL_CALLING,
                AgentState.COMPACTING,
                AgentState.RECOVERING,
                AgentState.WAITING,
                AgentState.COMPLETED,
                AgentState.FAILED,
                AgentState.CANCELLED,
            },
            AgentState.TOOL_CALLING: {
                AgentState.OBSERVING,
                AgentState.RECOVERING,
                AgentState.WAITING,
                AgentState.FAILED,
                AgentState.CANCELLED,
            },
            AgentState.COMPACTING: {AgentState.OBSERVING, AgentState.RECOVERING, AgentState.FAILED, AgentState.CANCELLED},
            AgentState.RECOVERING: {AgentState.OBSERVING, AgentState.FAILED, AgentState.CANCELLED},
            AgentState.WAITING: {AgentState.OBSERVING, AgentState.CANCELLED, AgentState.FAILED},
        }
        return next_state in allowed.get(self.state, set())
