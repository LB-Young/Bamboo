"""定义 LLM Provider 适配器共同使用的稳定接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

LLMRole = Literal["user", "assistant", "system", "tool"]


class LLMError(RuntimeError):
    """表示模型配置、网络请求或响应解析失败。"""


class LLMRequestError(LLMError):
    """表示模型平台拒绝请求或网络调用失败。"""


class LLMResponseError(LLMError):
    """表示模型平台返回了无法解析的响应。"""


@dataclass(frozen=True, slots=True)
class LLMToolCall:
    """表示模型请求执行的一次结构化工具调用。"""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """表示发送给模型的一条标准化消息。"""

    role: LLMRole
    content: str = ""
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    tool_name: str = ""


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """表示与具体模型平台无关的一次文本生成请求。"""

    messages: list[LLMMessage]
    system_prompt: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """表示模型平台返回的标准化文本结果。"""

    content: str
    model: str
    provider: str
    finish_reason: str = ""
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict, repr=False)


class LLMClient(ABC):
    """声明所有模型平台适配器必须实现的异步调用接口。"""

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """调用模型并返回标准化文本响应。"""
