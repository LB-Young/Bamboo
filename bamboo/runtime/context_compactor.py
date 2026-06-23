"""计算 Agent 上下文预算，并压缩 Session 中较早的活跃消息。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from bamboo.factory.message import Message
from bamboo.factory.session import Session
from bamboo.llms import LLMClient, LLMMessage, LLMRequest
from bamboo.llms.config import ModelConfig
from bamboo.runtime.prompt import AgentPrompt


class TokenCounter(Protocol):
    """声明上下文 Token 统计器接口，便于替换为平台精确 tokenizer。"""

    def count_request(self, request: LLMRequest) -> int:
        """统计一条完整模型请求预计占用的输入 Token。"""

    def count_text(self, text: str) -> int:
        """统计一段文本预计占用的 Token。"""


class HeuristicTokenCounter:
    """使用 UTF-8 字节数进行保守 Token 估算。"""

    def count_request(self, request: LLMRequest) -> int:
        """统计 system prompt、消息内容和消息结构开销。"""
        token_count = self.count_text(request.system_prompt)
        for message in request.messages:
            token_count += 4 + self.count_text(message.role) + self.count_text(message.content)
        return token_count + 3

    def count_text(self, text: str) -> int:
        """按每四个 UTF-8 字节约一个 Token 估算，空文本计零。"""
        if not text:
            return 0
        return max(1, math.ceil(len(text.encode("utf-8")) / 4))


@dataclass(frozen=True, slots=True)
class ContextBudgetPolicy:
    """配置上下文压缩阈值和每次压缩保留的最近消息。"""

    trigger_ratio: float = 0.5
    minimum_remaining_tokens: int = 20000
    preserve_recent_messages: int = 4
    max_compaction_passes: int = 2

    def __post_init__(self) -> None:
        """校验压缩策略，避免无效阈值导致无限压缩。"""
        if not 0 < self.trigger_ratio <= 1:
            raise ValueError("trigger_ratio must be in the range (0, 1]")
        if self.minimum_remaining_tokens < 0:
            raise ValueError("minimum_remaining_tokens cannot be negative")
        if self.preserve_recent_messages < 1:
            raise ValueError("preserve_recent_messages must be at least 1")
        if self.max_compaction_passes < 1:
            raise ValueError("max_compaction_passes must be at least 1")


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """记录一次 Prompt 的 Token 使用量和是否需要压缩。"""

    input_tokens: int
    remaining_tokens: int
    ratio: float
    should_compact: bool


class ContextCompactor:
    """使用当前 Agent 的模型将旧消息压缩为一条会话摘要。"""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        model_config: ModelConfig,
        token_counter: TokenCounter | None = None,
        policy: ContextBudgetPolicy | None = None,
    ) -> None:
        """初始化模型依赖、Token 统计器和压缩策略。"""
        self.llm_client = llm_client
        self.model_config = model_config
        self.token_counter = token_counter or HeuristicTokenCounter()
        self.policy = policy or ContextBudgetPolicy()

    def evaluate(self, prompt: AgentPrompt) -> ContextBudget:
        """根据最终 Prompt、模型窗口和输出预留计算是否需要压缩。"""
        input_tokens = self.token_counter.count_request(prompt.to_llm_request())
        remaining_tokens = self.model_config.context_window - input_tokens - self.model_config.max_tokens
        ratio = input_tokens / self.model_config.context_window
        should_compact = (
            ratio >= self.policy.trigger_ratio
            or remaining_tokens <= self.policy.minimum_remaining_tokens
        )
        return ContextBudget(
            input_tokens=input_tokens,
            remaining_tokens=remaining_tokens,
            ratio=ratio,
            should_compact=should_compact,
        )

    def has_compactable_messages(self, session: Session) -> bool:
        """判断活跃历史中是否存在可压缩且不属于最近保留区的消息。"""
        return bool(self._select_messages(session))

    async def compact(self, session: Session) -> bool:
        """压缩选中的旧消息；摘要无收益或没有候选消息时返回 False。"""
        selected_messages = self._select_messages(session)
        if not selected_messages:
            return False

        source_text = self._render_messages(selected_messages)
        response = await self.llm_client.complete(
            LLMRequest(
                system_prompt=(
                    "Compress the conversation history into a concise factual summary. "
                    "Preserve user requirements, decisions, errors, tool results and unresolved work. "
                    "Do not answer the user or add new information."
                ),
                messages=[LLMMessage(role="user", content=source_text)],
            )
        )
        summary = response.content.strip()
        if not summary or self.token_counter.count_text(summary) >= self.token_counter.count_text(source_text):
            return False

        session.replace_messages_with_summary(
            selected_messages,
            summary,
            agent_name="context-compactor",
        )
        return True

    def _select_messages(self, session: Session) -> list[Message]:
        """选择最近保留区之前的所有活跃消息作为本轮压缩候选。"""
        active_messages = session.active_messages()
        preserve_count = self.policy.preserve_recent_messages
        if len(active_messages) <= preserve_count:
            return []
        return active_messages[:-preserve_count]

    @staticmethod
    def _render_messages(messages: list[Message]) -> str:
        """按原始顺序渲染待压缩消息，并保留角色信息。"""
        return "\n\n".join(f"[{message.role}]\n{message.content}" for message in messages)
