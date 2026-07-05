"""验证 LLM Router、fallback 和 reactive compact。"""

from __future__ import annotations

import anyio

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import SessionCompactEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMClient, LLMContextLengthError, LLMFactory, LLMMessage, LLMRequest, LLMResponse
from bamboo.llms.base import LLMRequestError, classify_http_error
from bamboo.llms.router import LLMRouter
from bamboo.runtime.agent_runtime import AgentRuntime
from bamboo.runtime.context_compactor import ContextBudgetPolicy
from bamboo.runtime.runtime_context import RuntimeContextBuilder


def test_http_error_classification_marks_retryable_errors() -> None:
    """验证 provider 可把 HTTP 错误转成 Runtime 能判断的结构化类型。"""
    assert classify_http_error(429, "rate limit") == ("rate_limit", True)
    assert classify_http_error(500, "server exploded") == ("server_error", True)
    assert classify_http_error(401, "bad key") == ("auth", False)
    assert classify_http_error(400, "maximum context length exceeded") == ("context_length", False)


def test_llm_router_refuses_non_retryable_fallback() -> None:
    """auth/invalid 等非重试错误不会触发 fallback。"""
    factory = LLMFactory.from_mapping(_model_document())
    router = LLMRouter(factory)
    route = router.main_route("agent-model", fallback_model_name="fallback-model")
    assert not router.can_fallback(
        route,
        LLMRequestError("bad key", error_type="auth", retryable=False),
    )


def test_agent_runtime_fallbacks_once_for_retryable_main_model_error() -> None:
    """主模型遇到可重试错误时切到 fallback 模型，并记录任务 metadata。"""
    factory = LLMFactory.from_mapping(_model_document())
    primary_client = _FailingLLMClient(
        LLMRequestError("rate limited", error_type="rate_limit", retryable=True)
    )
    fallback_client = _StaticLLMClient(content="fallback answer", provider="gpt")
    factory.register_provider("deepseek", lambda config: primary_client, replace=True)
    factory.register_provider("gpt", lambda config: fallback_client, replace=True)
    config = _StubBambooConfig(
        _model_document(),
        agent_document={"model": "agent-model", "fallback_model": "fallback-model"},
    )
    task = TaskFactory(config=config).create(RunParams(message="hello", model="agent-model"))

    async def run_test() -> None:
        runtime_context = RuntimeContextBuilder(event_bus=EventBus(), llm_factory=factory).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        completed_task = await runtime.run(task)
        assert completed_task.output == "fallback answer"
        assert completed_task.metadata["fallback_used"] == "true"
        assert completed_task.metadata["fallback_from"] == "agent-model"
        assert completed_task.metadata["fallback_to"] == "fallback-model"
        assert completed_task.metadata["fallback_error_type"] == "rate_limit"
        assert completed_task.metadata["llm_model_name"] == "fallback-model"

    anyio.run(run_test)
    assert len(primary_client.requests) == 1
    assert len(fallback_client.requests) == 1


def test_reactive_compact_retries_once_after_context_length_error() -> None:
    """模型返回 context_length 后，Runtime 强制压缩并重试当前模型调用。"""
    document = _model_document()
    document["models"]["agent-model"]["context_window"] = 10000
    document["models"]["fallback-model"]["context_window"] = 10000
    document["models"]["summary-model"] = {
        "provider": "gpt",
        "model": "summary-provider-model",
        "api_key": "test-summary-key",
        "context_window": 10000,
        "max_tokens": 100,
    }
    factory = LLMFactory.from_mapping(document)
    agent_client = _ContextLengthOnceLLMClient()
    compaction_client = _StaticLLMClient(content="short summary", provider="gpt")
    factory.register_provider("deepseek", lambda config: agent_client, replace=True)
    factory.register_provider("gpt", lambda config: compaction_client, replace=True)
    config = _StubBambooConfig(
        document,
        agent_document={"model": "agent-model", "compaction_model": "summary-model"},
    )
    task = TaskFactory(config=config).create(RunParams(message="current question", model="agent-model"))
    task.session.add_message("assistant", "old answer " * 30)
    task.session.add_message("user", "old follow up " * 30)
    event_bus = EventBus()
    compact_events: list[SessionCompactEvent] = []
    event_bus.subscribe(lambda event: compact_events.append(event) if isinstance(event, SessionCompactEvent) else None)

    async def run_test() -> None:
        runtime_context = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=factory,
            compaction_policy=ContextBudgetPolicy(
                trigger_ratio=1.0,
                minimum_remaining_tokens=0,
                preserve_recent_messages=8,
                max_compaction_passes=1,
            ),
        ).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        completed_task = await runtime.run(task)
        assert completed_task.output == "answer after compact"
        assert completed_task.metadata["reactive_compaction_count"] == "1"
        assert completed_task.metadata["context_compaction_count"] == "1"

    anyio.run(run_test)
    assert len(agent_client.requests) == 2
    assert len(compaction_client.requests) == 1
    assert [event.reason for event in compact_events] == ["reactive"]
    assert any(message.message_type == "compaction" for message in task.session.messages)


def _model_document() -> dict:
    """创建包含主模型、fallback 模型的测试配置。"""
    return {
        "default_model": "agent-model",
        "models": {
            "agent-model": {
                "provider": "deepseek",
                "model": "agent-provider-model",
                "api_key": "test-agent-key",
                "base_url": "https://llm.test/v1",
                "max_tokens": 128,
            },
            "fallback-model": {
                "provider": "gpt",
                "model": "fallback-provider-model",
                "api_key": "test-fallback-key",
                "base_url": "https://llm.test/v1",
                "max_tokens": 128,
            },
        },
    }


class _StubBambooConfig:
    """为 RuntimeContextBuilder 测试提供内存配置。"""

    def __init__(self, models_document: dict, *, agent_document: dict | None = None) -> None:
        self.models_document = models_document
        self.agent_document = agent_document or {}

    def get(self, name: str, default: object = None) -> object:
        if name == "models":
            return self.models_document
        if name == "bamboo_main_agent":
            return self.agent_document
        return default


class _FailingLLMClient(LLMClient):
    """始终抛出指定异常的测试客户端。"""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        raise self.exc


class _StaticLLMClient(LLMClient):
    """记录请求并返回固定内容。"""

    def __init__(self, *, content: str, provider: str) -> None:
        self.content = content
        self.provider = provider
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            content=self.content,
            model=f"{self.provider}-provider-model",
            provider=self.provider,
            finish_reason="stop",
        )


class _ContextLengthOnceLLMClient(LLMClient):
    """第一次请求抛 context length，第二次返回答案。"""

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            raise LLMContextLengthError("maximum context length exceeded")
        assert any(isinstance(message, LLMMessage) for message in request.messages)
        return LLMResponse(
            content="answer after compact",
            model="agent-provider-model",
            provider="deepseek",
            finish_reason="stop",
        )

