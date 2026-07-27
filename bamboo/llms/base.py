"""定义 LLM Provider 适配器共同使用的稳定接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

LLMRole = Literal["user", "assistant", "system", "tool"]
LLMModelType = Literal["text", "vision", "image_generation", "image_edit", "video_generation"]
LLMErrorType = Literal[
    "rate_limit",
    "auth",
    "server_error",
    "timeout",
    "context_length",
    "invalid_response",
    "request",
    "unknown",
]


class LLMError(RuntimeError):
    """表示模型配置、网络请求或响应解析失败。"""

    def __init__(
        self,
        message: str,
        *,
        error_type: LLMErrorType = "unknown",
        retryable: bool = False,
    ) -> None:
        """保存可供 Runtime 路由判断的结构化错误信息。"""
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable


class LLMRequestError(LLMError):
    """表示模型平台拒绝请求或网络调用失败。"""


class LLMContextLengthError(LLMRequestError):
    """表示请求超过模型上下文窗口。"""

    def __init__(self, message: str) -> None:
        """上下文过长需要由 Runtime 先压缩，而不是直接 fallback。"""
        super().__init__(message, error_type="context_length", retryable=False)


class LLMResponseError(LLMError):
    """表示模型平台返回了无法解析的响应。"""

    def __init__(
        self,
        message: str,
        *,
        error_type: LLMErrorType = "invalid_response",
        retryable: bool = False,
    ) -> None:
        """响应解析错误默认不重试，避免 fallback 掩盖协议适配问题。"""
        super().__init__(message, error_type=error_type, retryable=retryable)


def classify_http_error(status_code: int, detail: str = "") -> tuple[LLMErrorType, bool]:
    """把常见 HTTP 状态映射为 Bamboo Runtime 可理解的 LLM 错误类型。"""
    lowered_detail = detail.lower()
    if status_code in {401, 403}:
        return "auth", False
    if status_code == 408:
        return "timeout", True
    if status_code == 429:
        return "rate_limit", True
    if status_code in {400, 413} and any(
        marker in lowered_detail
        for marker in ("context", "token", "too long", "maximum length", "max length")
    ):
        return "context_length", False
    if 500 <= status_code <= 599:
        return "server_error", True
    return "request", False


def classify_transport_error(error: BaseException) -> tuple[LLMErrorType, bool]:
    """把网络层异常映射为可 fallback 的请求错误。"""
    error_name = type(error).__name__.lower()
    if "timeout" in error_name:
        return "timeout", True
    return "request", True


@dataclass(frozen=True, slots=True)
class LLMImage:
    """表示一次发给模型的图片输入。"""

    source: str
    media_type: str = ""
    detail: str = "auto"


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
    images: list[LLMImage] = field(default_factory=list)
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
    reasoning_content: str = ""
    finish_reason: str = ""
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict, repr=False)


class LLMClient(ABC):
    """声明所有模型平台适配器必须实现的异步调用接口。"""

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """调用模型并返回标准化文本响应。"""
