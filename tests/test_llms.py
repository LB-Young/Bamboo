"""验证统一 LLM 工厂、Provider 协议和 AgentRuntime 接入。"""

from __future__ import annotations

import json

import anyio
import httpx
import pytest

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMClient, LLMFactory, LLMMessage, LLMRequest, LLMResponse, ModelCatalog, ModelConfigError
from bamboo.llms.providers import ClaudeClient, DeepSeekClient, GPTClient, MiniMaxClient
from bamboo.runtime.agent_runtime import AgentRuntime
from bamboo.runtime.task_runtime import TaskRuntime


def _model_document(provider: str, *, model_name: str = "test-model") -> dict:
    """创建单模型测试配置，避免依赖用户目录和真实密钥。"""
    return {
        "default_model": model_name,
        "models": {
            model_name: {
                "provider": provider,
                "model": "provider-model-id",
                "api_key": "test-api-key",
                "base_url": "https://llm.test/v1",
                "max_tokens": 128,
                "temperature": 0.1,
            }
        },
    }


def test_openai_compatible_client_builds_and_parses_request() -> None:
    """验证 GPT、DeepSeek、MiniMax 共用协议的请求和响应转换。"""
    catalog = ModelCatalog.from_mapping(_model_document("deepseek"))
    config = catalog.models["test-model"]

    async def run_test() -> None:
        """在异步环境中执行 mock HTTP 调用。"""
        def handler(request: httpx.Request) -> httpx.Response:
            """检查请求结构并返回模拟 Chat Completions 响应。"""
            payload = json.loads(request.content)
            assert request.url == "https://llm.test/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer test-api-key"
            assert payload["model"] == "provider-model-id"
            assert payload["messages"][0] == {"role": "system", "content": "system prompt"}
            assert payload["messages"][1] == {"role": "user", "content": "hello"}
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [{"message": {"content": "deepseek answer"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
                },
            )

        client = DeepSeekClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(
            LLMRequest(system_prompt="system prompt", messages=[LLMMessage(role="user", content="hello")])
        )
        assert response.content == "deepseek answer"
        assert response.provider == "deepseek"
        assert response.usage["total_tokens"] == 6

    anyio.run(run_test)


def test_anthropic_client_builds_and_parses_request() -> None:
    """验证 Claude Messages API 的请求头、请求体和文本块解析。"""
    catalog = ModelCatalog.from_mapping(_model_document("claude"))
    config = catalog.models["test-model"]

    async def run_test() -> None:
        """在异步环境中执行 mock Anthropic 调用。"""
        def handler(request: httpx.Request) -> httpx.Response:
            """检查 Anthropic 请求并返回模拟 content blocks。"""
            payload = json.loads(request.content)
            assert request.url == "https://llm.test/v1/messages"
            assert request.headers["x-api-key"] == "test-api-key"
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert payload["system"] == "system prompt"
            assert payload["messages"] == [{"role": "user", "content": "hello"}]
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "content": [{"type": "text", "text": "claude answer"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 4, "output_tokens": 2},
                },
            )

        client = ClaudeClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(
            LLMRequest(system_prompt="system prompt", messages=[LLMMessage(role="user", content="hello")])
        )
        assert response.content == "claude answer"
        assert response.provider == "claude"
        assert response.finish_reason == "end_turn"

    anyio.run(run_test)


def test_factory_uses_a_distinct_client_for_each_provider() -> None:
    """验证四个平台分别注册独立客户端，而不是直接复用同一 Provider 类。"""
    expected_clients = {
        "gpt": GPTClient,
        "deepseek": DeepSeekClient,
        "minimax": MiniMaxClient,
        "claude": ClaudeClient,
    }
    for provider, expected_client in expected_clients.items():
        factory = LLMFactory.from_mapping(_model_document(provider))
        assert type(factory.get_client("test-model")) is expected_client


def test_factory_allows_unused_models_without_api_key() -> None:
    """验证启动时可注册空 Key 模型，仅在该模型被选择时拒绝创建客户端。"""
    document = _model_document("deepseek", model_name="ready-model")
    document["models"]["unused-model"] = {
        "provider": "gpt",
        "model": "gpt-model-id",
        "api_key": "",
    }
    factory = LLMFactory.from_mapping(document)
    assert isinstance(factory.get_client("ready-model"), DeepSeekClient)
    with pytest.raises(ModelConfigError, match="api_key is empty"):
        factory.get_client("unused-model")


def test_agent_runtime_act_calls_registered_model() -> None:
    """验证 AgentRuntime 的 Act 阶段通过模型注册名调用统一工厂。"""
    factory = LLMFactory.from_mapping(_model_document("deepseek", model_name="agent-model"))
    stub_client = _StubLLMClient()
    factory.register_provider("deepseek", lambda config: stub_client, replace=True)
    run_params = RunParams(message="test question", model="agent-model")
    task = TaskFactory().create(run_params)

    async def run_test() -> None:
        """执行一轮 Agent OTA 流程并检查最终模型输出。"""
        runtime = AgentRuntime(event_bus=EventBus(), llm_factory=factory, model_name="agent-model")
        assert runtime.llm_client is stub_client
        assert runtime.model_name == "agent-model"
        completed_task = await runtime.run(task)
        assert completed_task.output == "real model response"
        assert completed_task.metadata["llm_model_name"] == "agent-model"
        assert completed_task.metadata["llm_provider"] == "deepseek"
        assert completed_task.session.messages[-1].agent_name == "llm:agent-model"
        assert stub_client.requests[0].messages[-1].content == "test question"

    anyio.run(run_test)


def test_task_runtime_initializes_llm_factory() -> None:
    """验证 TaskRuntime 构造时立即加载模型配置并保存共享工厂。"""
    config = _StubBambooConfig(_model_document("deepseek", model_name="runtime-model"))
    runtime = TaskRuntime(
        task_factory=TaskFactory(config=config),  # type: ignore[arg-type]
        event_bus=EventBus(),
    )
    assert runtime.llm_factory.default_model_name == "runtime-model"
    assert runtime.llm_factory.list_model_names() == ["runtime-model"]


class _StubLLMClient(LLMClient):
    """记录 Agent 发出的请求并返回固定模型响应。"""

    def __init__(self) -> None:
        """初始化请求记录列表。"""
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """记录请求并模拟一次真实模型平台响应。"""
        self.requests.append(request)
        return LLMResponse(
            content="real model response",
            model="provider-model-id",
            provider="deepseek",
            finish_reason="stop",
        )


class _StubBambooConfig:
    """为 TaskRuntime 初始化测试提供内存配置。"""

    def __init__(self, models_document: dict) -> None:
        """保存模拟的 models 配置文档。"""
        self.models_document = models_document

    def get(self, name: str, default: object = None) -> object:
        """模拟 BambooConfig.get，只返回 models 配置。"""
        if name == "models":
            return self.models_document
        return default
