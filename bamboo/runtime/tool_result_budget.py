"""Budget tool results before they enter model context."""

from __future__ import annotations

from dataclasses import dataclass

from bamboo.factory.session import Session
from bamboo.runtime.context_compactor import HeuristicTokenCounter, TokenCounter


@dataclass(frozen=True, slots=True)
class ToolResultBudgetPolicy:
    """Limits for tool result content stored in the active model context."""

    max_single_result_tokens: int = 12000
    max_total_result_tokens: int = 30000
    preserve_head_chars: int = 6000
    preserve_tail_chars: int = 3000
    truncation_notice: str = "[truncated: tool output exceeded context budget]"
    compacted_notice: str = "[compacted: older tool output exceeded context budget]"

    def __post_init__(self) -> None:
        if self.max_single_result_tokens < 1:
            raise ValueError("max_single_result_tokens must be positive")
        if self.max_total_result_tokens < 1:
            raise ValueError("max_total_result_tokens must be positive")
        if self.preserve_head_chars < 0:
            raise ValueError("preserve_head_chars cannot be negative")
        if self.preserve_tail_chars < 0:
            raise ValueError("preserve_tail_chars cannot be negative")


@dataclass(frozen=True, slots=True)
class BudgetedToolResult:
    """Tool result content split into UI output and model-context output."""

    original_content: str
    context_content: str
    original_length: int
    context_length: int
    original_tokens: int
    context_tokens: int
    truncated: bool

    @property
    def metadata(self) -> dict[str, int | bool]:
        """Return metadata suitable for storing on the session message/event."""
        return {
            "truncated": self.truncated,
            "original_length": self.original_length,
            "context_length": self.context_length,
            "original_tokens": self.original_tokens,
            "context_tokens": self.context_tokens,
        }


class ToolResultBudgeter:
    """Prepare tool output for session storage without changing tool execution."""

    def __init__(
        self,
        *,
        token_counter: TokenCounter | None = None,
        policy: ToolResultBudgetPolicy | None = None,
    ) -> None:
        self.token_counter = token_counter or HeuristicTokenCounter()
        self.policy = policy or ToolResultBudgetPolicy()

    def prepare_for_session(
        self,
        content: str,
        policy: ToolResultBudgetPolicy | None = None,
    ) -> BudgetedToolResult:
        """Return the content that should be written to model context."""
        active_policy = policy or self.policy
        original_tokens = self.token_counter.count_text(content)
        if original_tokens <= active_policy.max_single_result_tokens:
            return BudgetedToolResult(
                original_content=content,
                context_content=content,
                original_length=len(content),
                context_length=len(content),
                original_tokens=original_tokens,
                context_tokens=original_tokens,
                truncated=False,
            )

        context_content = self._truncate(content, active_policy)
        context_tokens = self.token_counter.count_text(context_content)
        return BudgetedToolResult(
            original_content=content,
            context_content=context_content,
            original_length=len(content),
            context_length=len(context_content),
            original_tokens=original_tokens,
            context_tokens=context_tokens,
            truncated=True,
        )

    def compact_old_tool_results(
        self,
        session: Session,
        policy: ToolResultBudgetPolicy | None = None,
    ) -> None:
        """Compact oldest active tool messages until total tool result budget fits."""
        active_policy = policy or self.policy
        tool_messages = [
            message
            for message in session.active_messages()
            if message.role == "tool" and not message.metadata.get("tool_result_budget_compacted")
        ]
        total_tokens = sum(self.token_counter.count_text(message.content) for message in tool_messages)
        if total_tokens <= active_policy.max_total_result_tokens:
            return

        for message in tool_messages:
            if total_tokens <= active_policy.max_total_result_tokens:
                break
            previous_content = message.content
            previous_tokens = self.token_counter.count_text(previous_content)
            message.content = (
                f"{active_policy.compacted_notice}\n"
                f"tool_name={message.tool_name or message.agent_name}\n"
                f"tool_call_id={message.tool_call_id}\n"
                f"original_length={len(previous_content)}\n"
                f"original_tokens={previous_tokens}"
            )
            message.metadata.update(
                {
                    "tool_result_budget_compacted": True,
                    "tool_result_budget_original_length": len(previous_content),
                    "tool_result_budget_original_tokens": previous_tokens,
                }
            )
            total_tokens -= previous_tokens
            total_tokens += self.token_counter.count_text(message.content)

    def _truncate(self, content: str, policy: ToolResultBudgetPolicy) -> str:
        """Preserve head and tail with a clear truncation notice in the middle."""
        head = content[: policy.preserve_head_chars] if policy.preserve_head_chars else ""
        tail = content[-policy.preserve_tail_chars :] if policy.preserve_tail_chars else ""
        omitted_chars = max(0, len(content) - len(head) - len(tail))
        notice = (
            f"\n{policy.truncation_notice} "
            f"omitted_chars={omitted_chars}\n"
        )
        context_content = f"{head}{notice}{tail}"
        while (
            self.token_counter.count_text(context_content) > policy.max_single_result_tokens
            and (head or tail)
        ):
            if head:
                head = head[: max(0, len(head) // 2)]
            elif tail:
                tail = tail[len(tail) // 2 :]
            else:
                break
            omitted_chars = max(0, len(content) - len(head) - len(tail))
            notice = (
                f"\n{policy.truncation_notice} "
                f"omitted_chars={omitted_chars}\n"
            )
            context_content = f"{head}{notice}{tail}"
        return context_content
