"""计算 Agent 上下文预算，并压缩 Session 中较早的活跃消息。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Protocol

from bamboo.factory.message import Message
from bamboo.factory.session import Session
from bamboo.llms import LLMClient, LLMMessage, LLMRequest
from bamboo.llms.config import ModelConfig
from bamboo.llms.router import LLMRoute, LLMRouter
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
        token_count += self.count_text(json.dumps(request.tools, ensure_ascii=False))
        for message in request.messages:
            token_count += 4 + self.count_text(message.role) + self.count_text(message.content)
            token_count += self.count_text(
                json.dumps(
                    [
                        {"id": call.id, "name": call.name, "arguments": call.arguments}
                        for call in message.tool_calls
                    ],
                    ensure_ascii=False,
                )
            )
            token_count += self.count_text(message.tool_call_id)
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
        llm_router: LLMRouter | None = None,
        route: LLMRoute | None = None,
        token_counter: TokenCounter | None = None,
        policy: ContextBudgetPolicy | None = None,
    ) -> None:
        """初始化模型依赖、Token 统计器和压缩策略。"""
        self.llm_client = llm_client
        self.model_config = model_config
        self.llm_router = llm_router
        self.route = route
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

    async def compact(self, session: Session, *, force: bool = False) -> bool:
        """压缩选中的旧消息；force 模式会在摘要无收益时降级停用低价值旧消息。"""
        selected_messages = self._select_messages(session)
        if force and not selected_messages:
            selected_messages = self._select_force_messages(session)
        if not selected_messages:
            return False

        source_text = self._render_messages(selected_messages)
        try:
            response = await self._complete_with_fallback(source_text)
        except Exception:
            if force:
                return self._drop_low_value_message(session)
            raise
        summary = response.content.strip()
        if not summary or self.token_counter.count_text(summary) >= self.token_counter.count_text(source_text):
            if force:
                return self._drop_low_value_message(session)
            return False

        session.replace_messages_with_summary(
            selected_messages,
            summary,
            agent_name="context-compactor",
        )
        return True

    async def _complete_with_fallback(self, source_text: str):
        request = LLMRequest(
            system_prompt=(
                "Compress the conversation history into a concise factual summary. "
                "Preserve user requirements, decisions, errors, tool results and unresolved work. "
                "Do not answer the user or add new information."
            ),
            messages=[LLMMessage(role="user", content=source_text)],
        )
        try:
            return await self.llm_client.complete(request)
        except Exception as exc:
            if self.llm_router is None or self.route is None or not self.llm_router.can_fallback(self.route, exc):
                raise
            self.llm_router.activate_fallback(self.route)
            self.llm_client = self.llm_router.client_for(self.route)
            return await self.llm_client.complete(request)

    def _select_messages(self, session: Session) -> list[Message]:
        """选择最近保留区之前的所有活跃消息作为本轮压缩候选。"""
        active_messages = session.active_messages()
        preserve_count = self.policy.preserve_recent_messages
        if len(active_messages) <= preserve_count:
            return []
        return active_messages[:-preserve_count]

    def _select_force_messages(self, session: Session) -> list[Message]:
        """reactive compact 使用：至少保留最后一条活跃消息，尽量压缩其之前的历史。"""
        active_messages = session.active_messages()
        if len(active_messages) <= 1:
            return []
        return active_messages[:-1]

    @staticmethod
    def _drop_low_value_message(session: Session) -> bool:
        """reactive compact 降级：停用最旧的普通 assistant 输出或成对工具结果。"""
        active_messages = session.active_messages()
        protected_id = active_messages[-1].message_id if active_messages else ""
        for message in active_messages:
            if message.message_id == protected_id:
                continue
            if message.role == "assistant" and not message.tool_calls and message.message_type == "normal":
                message.metadata["reactive_compact_dropped"] = True
                message.mark_as_compressed()
                return True

        for message in active_messages:
            if message.message_id == protected_id or message.role != "tool":
                continue
            paired_assistant = _find_tool_call_assistant(session, message.tool_call_id)
            if paired_assistant is not None:
                paired_assistant.metadata["reactive_compact_dropped"] = True
                paired_assistant.mark_as_compressed()
            message.metadata["reactive_compact_dropped"] = True
            message.mark_as_compressed()
            return True
        return False

    @staticmethod
    def _render_messages(messages: list[Message]) -> str:
        """按原始顺序渲染待压缩消息，并保留角色和工具调用信息。"""
        rendered_messages: list[str] = []
        for message in messages:
            sections = [f"[{message.role}]", message.content]
            if message.tool_calls:
                sections.append(
                    "tool_calls="
                    + json.dumps(
                        [
                            {"id": call.id, "name": call.name, "arguments": call.arguments}
                            for call in message.tool_calls
                        ],
                        ensure_ascii=False,
                    )
                )
            if message.tool_call_id:
                sections.append(f"tool_call_id={message.tool_call_id}")
            rendered_messages.append("\n".join(section for section in sections if section))
        return "\n\n".join(rendered_messages)


def _find_tool_call_assistant(session: Session, tool_call_id: str) -> Message | None:
    """查找产生指定 tool_call_id 的 assistant 消息，便于降级时成对停用。"""
    if not tool_call_id:
        return None
    for message in session.active_messages():
        if message.role != "assistant":
            continue
        if any(tool_call.id == tool_call_id for tool_call in message.tool_calls):
            return message
    return None
