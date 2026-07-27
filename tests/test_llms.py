"""验证统一 LLM 工厂、Provider 协议和 AgentRuntime 接入。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import anyio
import httpx
import pytest

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import (
    ReasoningDeltaEvent,
    SessionCompactEvent,
    SessionStatusChangeEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
)
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import (
    LLMClient,
    LLMFactory,
    LLMImage,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    ModelCatalog,
    ModelConfigError,
)
from bamboo.llms.providers import (
    AliyunClient,
    ClaudeClient,
    DeepSeekClient,
    GPTClient,
    KimiClient,
    MimoClient,
    MiniMaxClient,
    OllamaClient,
    OpenRouterClient,
    VLLMClient,
)
from bamboo.runtime.agent_runtime import AgentRuntime
from bamboo.runtime.context_compactor import ContextBudgetPolicy
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.runtime.task_runtime import TaskRuntime
from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.registry import ToolRegistry


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


def test_aliyun_client_uses_openai_compatible_endpoint() -> None:
    """验证 Aliyun 文本模型走百炼 OpenAI-compatible endpoint。"""
    catalog = ModelCatalog.from_mapping(_model_document("aliyun"))
    config = catalog.models["test-model"]

    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == "https://llm.test/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer test-api-key"
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [{"message": {"content": "aliyun answer"}, "finish_reason": "stop"}],
                },
            )

        client = AliyunClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(LLMRequest(messages=[LLMMessage(role="user", content="hello")]))

        assert response.content == "aliyun answer"
        assert response.provider == "aliyun"

    anyio.run(run_test)


def test_openrouter_client_uses_openai_compatible_endpoint() -> None:
    """验证 OpenRouter 文本模型走 OpenAI-compatible endpoint。"""
    catalog = ModelCatalog.from_mapping(_model_document("openrouter"))
    config = catalog.models["test-model"]

    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == "https://llm.test/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer test-api-key"
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [{"message": {"content": "openrouter answer"}, "finish_reason": "stop"}],
                },
            )

        client = OpenRouterClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(LLMRequest(messages=[LLMMessage(role="user", content="hello")]))

        assert response.content == "openrouter answer"
        assert response.provider == "openrouter"

    anyio.run(run_test)


def test_openai_compatible_client_serializes_image_content(tmp_path: Path) -> None:
    """验证 OpenAI-compatible 请求能发送 text + image_url content blocks。"""
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    catalog = ModelCatalog.from_mapping(_model_document("kimi"))
    config = catalog.models["test-model"]

    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            content = payload["messages"][0]["content"]
            assert content[0] == {"type": "text", "text": "describe this"}
            assert content[1]["type"] == "image_url"
            assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [{"message": {"content": "image answer"}, "finish_reason": "stop"}],
                },
            )

        client = KimiClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(
            LLMRequest(
                messages=[
                    LLMMessage(
                        role="user",
                        content="describe this",
                        images=[LLMImage(source=str(image_path), media_type="image/png")],
                    )
                ]
            )
        )
        assert response.content == "image answer"

    anyio.run(run_test)


def test_local_openai_compatible_client_allows_empty_api_key() -> None:
    """验证本地 OpenAI-compatible Provider 支持免密调用。"""
    document = _model_document("ollama")
    document["models"]["test-model"]["api_key"] = ""
    document["models"]["test-model"]["base_url"] = ""
    catalog = ModelCatalog.from_mapping(document)
    config = catalog.models["test-model"].resolve_environment()

    async def run_test() -> None:
        """检查本地默认地址和请求头。"""
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == "http://localhost:11434/v1/chat/completions"
            assert "authorization" not in request.headers
            payload = json.loads(request.content)
            assert payload["model"] == "provider-model-id"
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [{"message": {"content": "local answer"}, "finish_reason": "stop"}],
                },
            )

        client = OllamaClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(
            LLMRequest(messages=[LLMMessage(role="user", content="hello local")])
        )
        assert response.content == "local answer"
        assert response.provider == "ollama"

    anyio.run(run_test)


def test_mimo_client_uses_documented_headers_and_token_field() -> None:
    """验证 MiMo Provider 使用 api-key 鉴权和 max_completion_tokens 字段。"""
    document = _model_document("mimo")
    document["models"]["test-model"]["base_url"] = ""
    config = ModelCatalog.from_mapping(document).models["test-model"].resolve_environment()

    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            assert request.url == "https://api.xiaomimimo.com/v1/chat/completions"
            assert request.headers["api-key"] == "test-api-key"
            assert "authorization" not in request.headers
            assert payload["max_completion_tokens"] == 128
            assert "max_tokens" not in payload
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [{"message": {"content": "mimo answer"}, "finish_reason": "stop"}],
                },
            )

        client = MimoClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(LLMRequest(messages=[LLMMessage(role="user", content="hello")]))
        assert response.content == "mimo answer"
        assert response.provider == "mimo"

    anyio.run(run_test)


def test_kimi_client_uses_default_endpoint_and_k3_reasoning_effort() -> None:
    """验证 Kimi Provider 默认 endpoint 和 K3 必需的 reasoning_effort。"""
    document = _model_document("kimi")
    document["models"]["test-model"]["base_url"] = ""
    document["models"]["test-model"]["model"] = "kimi-k3"
    document["models"]["test-model"].pop("temperature")
    config = ModelCatalog.from_mapping(document).models["test-model"].resolve_environment()

    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            assert request.url == "https://api.moonshot.cn/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer test-api-key"
            assert payload["model"] == "kimi-k3"
            assert payload["reasoning_effort"] == "max"
            assert "temperature" not in payload
            return httpx.Response(
                200,
                json={
                    "model": "kimi-k3",
                    "choices": [{"message": {"content": "kimi answer"}, "finish_reason": "stop"}],
                },
            )

        client = KimiClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(LLMRequest(messages=[LLMMessage(role="user", content="hello")]))
        assert response.content == "kimi answer"
        assert response.provider == "kimi"

    anyio.run(run_test)


def test_kimi_client_respects_configured_extra_body() -> None:
    """验证 models.yaml 中的 extra_body 会作为顶层参数透传给 Kimi。"""
    document = _model_document("kimi")
    document["models"]["test-model"]["model"] = "kimi-k3"
    document["models"]["test-model"]["extra_body"] = {"reasoning_effort": "max"}
    config = ModelCatalog.from_mapping(document).models["test-model"].resolve_environment()

    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            assert payload["reasoning_effort"] == "max"
            return httpx.Response(
                200,
                json={
                    "model": "kimi-k3",
                    "choices": [{"message": {"content": "configured"}, "finish_reason": "stop"}],
                },
            )

        client = KimiClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(LLMRequest(messages=[LLMMessage(role="user", content="hello")]))
        assert response.content == "configured"

    anyio.run(run_test)


def test_openai_compatible_client_extracts_reasoning_content_field() -> None:
    """验证 OpenAI-compatible 响应的 reasoning_content 会和最终答案分离。"""
    config = ModelCatalog.from_mapping(_model_document("deepseek")).models["test-model"]

    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [
                        {
                            "message": {
                                "reasoning_content": "先分析问题。",
                                "content": "最终答案。",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

        client = DeepSeekClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(LLMRequest(messages=[LLMMessage(role="user", content="hello")]))
        assert response.reasoning_content == "先分析问题。"
        assert response.content == "最终答案。"

    anyio.run(run_test)


def test_openai_compatible_client_splits_tagged_reasoning_from_content() -> None:
    """验证混在正文里的 think 标签会被拆成 reasoning 和最终答案。"""
    config = ModelCatalog.from_mapping(_model_document("vllm")).models["test-model"]

    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [
                        {
                            "message": {
                                "content": "<think>先想一下。</think>\n最终答案。",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

        client = VLLMClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(LLMRequest(messages=[LLMMessage(role="user", content="hello")]))
        assert response.reasoning_content == "先想一下。"
        assert response.content == "最终答案。"

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
            assert payload["messages"] == [
                {"role": "user", "content": [{"type": "text", "text": "hello"}]}
            ]
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


def test_anthropic_client_serializes_image_content(tmp_path: Path) -> None:
    """验证 Claude Messages 请求能发送 Anthropic image block。"""
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"\xff\xd8\xff")
    catalog = ModelCatalog.from_mapping(_model_document("claude"))
    config = catalog.models["test-model"]

    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            blocks = payload["messages"][0]["content"]
            assert blocks[0] == {"type": "text", "text": "describe this"}
            assert blocks[1]["type"] == "image"
            assert blocks[1]["source"]["type"] == "base64"
            assert blocks[1]["source"]["media_type"] == "image/jpeg"
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "content": [{"type": "text", "text": "image answer"}],
                    "stop_reason": "end_turn",
                },
            )

        client = ClaudeClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(
            LLMRequest(
                messages=[
                    LLMMessage(
                        role="user",
                        content="describe this",
                        images=[LLMImage(source=str(image_path), media_type="image/jpeg")],
                    )
                ]
            )
        )
        assert response.content == "image answer"

    anyio.run(run_test)


def test_openai_compatible_client_parses_tool_call() -> None:
    """验证 OpenAI-compatible Provider 发送工具 Schema 并解析 function tool_call。"""
    config = ModelCatalog.from_mapping(_model_document("deepseek")).models["test-model"]

    async def run_test() -> None:
        """执行一次 mock function calling 请求。"""
        def handler(request: httpx.Request) -> httpx.Response:
            """检查工具 Schema 并返回结构化 Tool Call。"""
            payload = json.loads(request.content)
            assert payload["tools"][0]["function"]["name"] == "echo"
            assert payload["tools"][0]["function"]["parameters"]["required"] == ["value"]
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "type": "function",
                                        "function": {
                                            "name": "echo",
                                            "arguments": '{"value":"hello"}',
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                },
            )

        client = DeepSeekClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(
            LLMRequest(
                messages=[LLMMessage(role="user", content="echo hello")],
                tools=[
                    {
                        "name": "echo",
                        "description": "Echo a value.",
                        "input_schema": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                        },
                    }
                ],
            )
        )
        assert response.content == ""
        assert response.tool_calls == [LLMToolCall(id="call-1", name="echo", arguments={"value": "hello"})]

    anyio.run(run_test)


def test_anthropic_client_parses_tool_use() -> None:
    """验证 Claude Provider 发送工具 Schema 并解析 tool_use block。"""
    config = ModelCatalog.from_mapping(_model_document("claude")).models["test-model"]

    async def run_test() -> None:
        """执行一次 mock Claude tool_use 请求。"""
        def handler(request: httpx.Request) -> httpx.Response:
            """检查 Claude tools 并返回 tool_use block。"""
            payload = json.loads(request.content)
            assert payload["tools"][0]["name"] == "echo"
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu-1",
                            "name": "echo",
                            "input": {"value": "hello"},
                        }
                    ],
                    "stop_reason": "tool_use",
                },
            )

        client = ClaudeClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(
            LLMRequest(
                messages=[LLMMessage(role="user", content="echo hello")],
                tools=[{"name": "echo", "description": "Echo.", "input_schema": {"type": "object"}}],
            )
        )
        assert response.tool_calls == [
            LLMToolCall(id="toolu-1", name="echo", arguments={"value": "hello"})
        ]

    anyio.run(run_test)


def test_openai_compatible_client_serializes_tool_result_history() -> None:
    """验证 OpenAI-compatible 下一轮请求保留 assistant Tool Call 和 tool result。"""
    config = ModelCatalog.from_mapping(_model_document("deepseek")).models["test-model"]
    tool_call = LLMToolCall(id="call-1", name="echo", arguments={"value": "hello"})

    async def run_test() -> None:
        """发送包含工具历史的 mock 请求。"""
        def handler(request: httpx.Request) -> httpx.Response:
            """检查 OpenAI 工具历史消息格式。"""
            messages = json.loads(request.content)["messages"]
            assert messages[1]["role"] == "assistant"
            assert messages[1]["tool_calls"][0]["function"]["name"] == "echo"
            assert json.loads(messages[1]["tool_calls"][0]["function"]["arguments"]) == {"value": "hello"}
            assert messages[2] == {
                "role": "tool",
                "content": "echoed: hello",
                "tool_call_id": "call-1",
            }
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "choices": [{"message": {"content": "done"}, "finish_reason": "stop"}],
                },
            )

        client = DeepSeekClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(
            LLMRequest(
                system_prompt="system",
                messages=[
                    LLMMessage(role="assistant", tool_calls=[tool_call]),
                    LLMMessage(
                        role="tool",
                        content="echoed: hello",
                        tool_call_id="call-1",
                        tool_name="echo",
                    ),
                ],
            )
        )
        assert response.content == "done"

    anyio.run(run_test)


def test_anthropic_client_serializes_tool_result_history() -> None:
    """验证 Claude 下一轮请求保留 tool_use 和对应 tool_result blocks。"""
    config = ModelCatalog.from_mapping(_model_document("claude")).models["test-model"]
    tool_call = LLMToolCall(id="toolu-1", name="echo", arguments={"value": "hello"})

    async def run_test() -> None:
        """发送包含 Claude 工具历史的 mock 请求。"""
        def handler(request: httpx.Request) -> httpx.Response:
            """检查 Claude 工具历史 content blocks。"""
            messages = json.loads(request.content)["messages"]
            assert messages == [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu-1",
                            "name": "echo",
                            "input": {"value": "hello"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu-1",
                            "content": "echoed: hello",
                        }
                    ],
                },
            ]
            return httpx.Response(
                200,
                json={
                    "model": "provider-model-id",
                    "content": [{"type": "text", "text": "done"}],
                    "stop_reason": "end_turn",
                },
            )

        client = ClaudeClient(config, transport=httpx.MockTransport(handler))
        response = await client.complete(
            LLMRequest(
                messages=[
                    LLMMessage(role="assistant", tool_calls=[tool_call]),
                    LLMMessage(role="tool", content="echoed: hello", tool_call_id="toolu-1", tool_name="echo"),
                ]
            )
        )
        assert response.content == "done"

    anyio.run(run_test)


def test_factory_uses_a_distinct_client_for_each_provider() -> None:
    """验证各平台分别注册独立客户端，而不是直接复用同一 Provider 类。"""
    expected_clients = {
        "gpt": GPTClient,
        "deepseek": DeepSeekClient,
        "kimi": KimiClient,
        "minimax": MiniMaxClient,
        "mimo": MimoClient,
        "claude": ClaudeClient,
        "ollama": OllamaClient,
        "vllm": VLLMClient,
    }
    for provider, expected_client in expected_clients.items():
        document = _model_document(provider)
        if provider in {"ollama", "vllm"}:
            document["models"]["test-model"]["api_key"] = ""
        factory = LLMFactory.from_mapping(document)
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
        event_bus = EventBus()
        runtime_context = RuntimeContextBuilder(event_bus=event_bus, llm_factory=factory).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        assert runtime.llm_client is stub_client
        assert runtime.compaction_llm_client is stub_client
        assert runtime.model_name == "agent-model"
        assert runtime.compaction_model_name == "agent-model"
        completed_task = await runtime.run(task)
        assert completed_task.output == "real model response"
        assert completed_task.metadata["llm_model_name"] == "agent-model"
        assert completed_task.metadata["llm_provider"] == "deepseek"
        assert completed_task.session.messages[-1].agent_name == "llm:agent-model"
        assert stub_client.requests[0].messages[-1].content == "test question"

    anyio.run(run_test)


def test_task_runtime_initializes_llm_factory() -> None:
    """验证 TaskRuntime 构造时立即加载模型配置并保存共享工厂。"""
    document = _model_document("deepseek", model_name="runtime-model")
    document["models"]["summary-model"] = {
        "provider": "gpt",
        "model": "gpt-summary-model",
        "api_key": "test-summary-key",
    }
    config = _StubBambooConfig(
        document,
        agent_document={"model": "runtime-model", "compaction_model": "summary-model"},
    )
    runtime = TaskRuntime(
        task_factory=TaskFactory(config=config),  # type: ignore[arg-type]
        event_bus=EventBus(),
    )
    assert runtime.llm_factory.default_model_name == "runtime-model"
    assert runtime.llm_factory.list_model_names() == ["runtime-model", "summary-model"]
    task = runtime.task_factory.create(RunParams(message=""))
    agent = runtime._create_agent(task)
    assert agent.model_name == "runtime-model"
    assert agent.compaction_model_name == "summary-model"


def test_agent_runtime_compacts_context_before_model_call() -> None:
    """使用低阈值验证上下文压缩、消息替换、事件和最终模型调用效果。"""
    document = _model_document("deepseek", model_name="compact-model")
    document["models"]["compact-model"]["context_window"] = 1000
    document["models"]["compact-model"]["max_tokens"] = 100
    document["models"]["summary-model"] = {
        "provider": "gpt",
        "model": "gpt-summary-model",
        "api_key": "test-summary-key",
        "context_window": 1000,
        "max_tokens": 100,
    }
    factory = LLMFactory.from_mapping(document)
    agent_client = _RecordingLLMClient(content="final answer", provider="deepseek")
    compaction_client = _RecordingLLMClient(content="short history summary", provider="gpt")
    factory.register_provider("deepseek", lambda config: agent_client, replace=True)
    factory.register_provider("gpt", lambda config: compaction_client, replace=True)
    task = TaskFactory().create(RunParams(message="", model="compact-model"))
    task.session.add_message("user", "old requirement " * 20)
    task.session.add_message("assistant", "old implementation detail " * 20)
    task.session.add_message("user", "old correction " * 20)
    task.session.add_message("assistant", "old result " * 20)
    task.session.add_message("user", "current question")
    event_bus = EventBus()
    compact_events: list[SessionCompactEvent] = []
    states: list[str] = []

    def collect_event(event: object) -> None:
        """收集压缩事件和状态变化，验证运行时执行顺序。"""
        if isinstance(event, SessionCompactEvent):
            compact_events.append(event)
        if isinstance(event, SessionStatusChangeEvent):
            states.append(event.status)

    event_bus.subscribe(collect_event)

    async def run_test() -> None:
        """执行一次低阈值 OTA 循环并检查压缩后的 Session。"""
        runtime_context = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=factory,
            compaction_model_name="summary-model",
            compaction_policy=ContextBudgetPolicy(
                trigger_ratio=0.1,
                minimum_remaining_tokens=0,
                preserve_recent_messages=1,
                max_compaction_passes=1,
            ),
            token_counter=_CharacterTokenCounter(),
        ).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        completed_task = await runtime.run(task)
        assert completed_task.output == "final answer"
        assert runtime.run_state.compaction_count == 1
        assert completed_task.metadata["context_compaction_count"] == "1"
        assert completed_task.metadata["context_compaction_model"] == "summary-model"

    anyio.run(run_test)

    assert len(compaction_client.requests) == 1
    assert compaction_client.requests[0].system_prompt.startswith("Compress the conversation history")
    assert len(agent_client.requests) == 1
    final_request = agent_client.requests[0]
    assert any("[conversation-summary]" in message.content for message in final_request.messages)
    assert all("old implementation detail" not in message.content for message in final_request.messages)
    assert sum(message.compressed for message in task.session.messages) == 4
    assert len(compact_events) == 1
    assert compact_events[0].after_token_count < compact_events[0].before_token_count
    assert "compacting" in states


def test_context_compaction_uses_production_thresholds_by_default() -> None:
    """确认低阈值仅用于测试，生产默认保持 50% 和剩余 20k。"""
    policy = ContextBudgetPolicy()
    assert policy.trigger_ratio == 0.5
    assert policy.minimum_remaining_tokens == 20000


def test_agent_runtime_executes_tool_and_continues_ota_loop() -> None:
    """验证 Think 返回 Tool Call 后执行工具并继续下一轮，直到模型返回最终结论。"""
    factory = LLMFactory.from_mapping(_model_document("deepseek", model_name="tool-model"))
    llm_client = _ToolLoopLLMClient()
    factory.register_provider("deepseek", lambda config: llm_client, replace=True)
    tool_registry = ToolRegistry()
    echo_tool = _EchoTool()
    tool_registry.register(echo_tool, source="test")
    event_bus = EventBus()
    emitted_events: list[object] = []
    event_bus.subscribe(emitted_events.append)
    task = TaskFactory().create(RunParams(message="请用 echo 工具处理 hello", model="tool-model"))

    async def run_test() -> None:
        """执行包含一次工具调用和一次最终回答的两轮 OTA。"""
        runtime_context = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=factory,
            tool_registry=tool_registry,
        ).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        completed_task = await runtime.run(task)
        assert completed_task.output == "工具返回了 echoed: hello"
        assert runtime.run_state.iteration == 2
        assert completed_task.metadata["tool_call_count"] == "1"

    anyio.run(run_test)

    assert echo_tool.values == ["hello"]
    assert len(llm_client.requests) == 2
    second_messages = llm_client.requests[1].messages
    assert [message.role for message in second_messages] == ["user", "assistant", "tool"]
    assert second_messages[1].tool_calls[0].id == "call-echo-1"
    assert second_messages[2].tool_call_id == "call-echo-1"
    assert second_messages[2].content == "echoed: hello"
    assert any(isinstance(event, ToolCallEvent) for event in emitted_events)
    assert any(isinstance(event, ToolResultEvent) for event in emitted_events)
    assert any(
        isinstance(event, SessionStatusChangeEvent) and event.status == "tool_calling"
        for event in emitted_events
    )


def test_agent_runtime_times_out_slow_tool_and_continues_ota_loop() -> None:
    """验证工具超时会写入 tool error，并让下一轮模型继续决策。"""
    config = _StubBambooConfig(
        _model_document("deepseek", model_name="tool-timeout-model"),
        agent_document={"tool_call_timeout_seconds": 0.01},
    )
    factory = LLMFactory.from_mapping(config.models_document)
    llm_client = _TimeoutToolLoopLLMClient()
    factory.register_provider("deepseek", lambda model_config: llm_client, replace=True)
    tool_registry = ToolRegistry()
    slow_tool = _SlowTool()
    tool_registry.register(slow_tool, source="test")
    event_bus = EventBus()
    emitted_events: list[object] = []
    event_bus.subscribe(emitted_events.append)
    task = TaskFactory(config=config).create(RunParams(message="try slow tool", model="tool-timeout-model"))

    async def run_test() -> None:
        runtime_context = RuntimeContextBuilder(
            event_bus=event_bus,
            llm_factory=factory,
            tool_registry=tool_registry,
        ).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        completed_task = await runtime.run(task)
        assert completed_task.output == "工具超时，改用替代方案"
        assert runtime.run_state.iteration == 2

    anyio.run(run_test)

    assert slow_tool.started is True
    assert len(llm_client.requests) == 2
    second_messages = llm_client.requests[1].messages
    assert [message.role for message in second_messages] == ["user", "assistant", "tool"]
    assert "Tool call timed out after" in second_messages[2].content
    assert any(isinstance(event, ToolErrorEvent) and "timed out" in event.error for event in emitted_events)
    assert not any(isinstance(event, ToolResultEvent) and event.tool_name == "slow" for event in emitted_events)


def test_agent_runtime_uses_tool_timeout_override() -> None:
    """验证单个工具可以覆盖全局 tool-call 超时。"""
    config = _StubBambooConfig(
        _model_document("deepseek", model_name="tool-timeout-override-model"),
        agent_document={"tool_call_timeout_seconds": 0.01},
    )
    factory = LLMFactory.from_mapping(config.models_document)
    llm_client = _TimeoutOverrideToolLoopLLMClient()
    factory.register_provider("deepseek", lambda model_config: llm_client, replace=True)
    tool_registry = ToolRegistry()
    slow_tool = _SlowButAllowedTool()
    tool_registry.register(slow_tool, source="test")
    task = TaskFactory(config=config).create(RunParams(message="try slow allowed", model="tool-timeout-override-model"))

    async def run_test() -> None:
        runtime_context = RuntimeContextBuilder(
            event_bus=EventBus(),
            llm_factory=factory,
            tool_registry=tool_registry,
        ).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        completed_task = await runtime.run(task)
        assert completed_task.output == "工具完成"

    anyio.run(run_test)

    assert slow_tool.started is True
    assert len(llm_client.requests) == 2


def test_agent_runtime_emits_reasoning_separately_from_final_text() -> None:
    """验证推理过程通过 reasoning 事件输出，assistant 正文只保留最终答案。"""
    factory = LLMFactory.from_mapping(_model_document("deepseek", model_name="reasoning-model"))
    llm_client = _RecordingLLMClient(content="最终答案", provider="deepseek", reasoning_content="推理过程")
    factory.register_provider("deepseek", lambda model_config: llm_client, replace=True)
    event_bus = EventBus()
    emitted_events: list[object] = []
    event_bus.subscribe(emitted_events.append)
    task = TaskFactory().create(RunParams(message="question", model="reasoning-model"))

    async def run_test() -> None:
        runtime_context = RuntimeContextBuilder(event_bus=event_bus, llm_factory=factory).build(task)
        runtime = AgentRuntime(runtime_context=runtime_context)
        completed_task = await runtime.run(task)
        assert completed_task.output == "最终答案"

    anyio.run(run_test)

    assert task.session.messages[-1].content == "最终答案"
    assert task.session.messages[-1].metadata["reasoning_content"] == "推理过程"
    assert any(isinstance(event, ReasoningDeltaEvent) and event.delta == "推理过程" for event in emitted_events)


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

    def __init__(self, models_document: dict, *, agent_document: dict | None = None) -> None:
        """保存模拟的 models 配置文档。"""
        self.models_document = models_document
        self.agent_document = agent_document or {}

    def get(self, name: str, default: object = None) -> object:
        """模拟 BambooConfig.get，只返回 models 配置。"""
        if name == "models":
            return self.models_document
        if name == "bamboo_main_agent":
            return self.agent_document
        return default


class _RecordingLLMClient(LLMClient):
    """记录请求并返回指定内容，用于区分执行模型和压缩模型。"""

    def __init__(self, *, content: str, provider: str, reasoning_content: str = "") -> None:
        """初始化固定响应内容、平台名和请求记录。"""
        self.content = content
        self.provider = provider
        self.reasoning_content = reasoning_content
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """记录请求并返回当前客户端的固定模型响应。"""
        self.requests.append(request)
        return LLMResponse(
            content=self.content,
            model="provider-model-id",
            provider=self.provider,
            reasoning_content=self.reasoning_content,
            finish_reason="stop",
        )


class _CharacterTokenCounter:
    """使用字符数作为测试 Token，确保低阈值测试结果稳定。"""

    def count_request(self, request: LLMRequest) -> int:
        """统计测试请求的 system prompt、角色和内容字符数。"""
        return len(request.system_prompt) + sum(
            len(message.role) + len(message.content) for message in request.messages
        )

    def count_text(self, text: str) -> int:
        """返回文本字符数作为测试 Token 数。"""
        return len(text)


class _EchoTool(Tool):
    """返回输入值并记录调用参数的测试工具。"""

    name = "echo"
    description = "Echo a string value."

    def __init__(self) -> None:
        """初始化工具调用记录。"""
        self.values: list[str] = []

    def input_schema(self) -> dict:
        """声明 echo 工具需要一个字符串 value。"""
        return {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        }

    async def execute(self, value: str) -> ToolResult:
        """记录并原样返回输入值。"""
        self.values.append(value)
        return ToolResult(content=f"echoed: {value}")


class _SlowTool(Tool):
    name = "slow"
    description = "Sleep longer than the runtime timeout."

    def __init__(self) -> None:
        self.started = False

    async def execute(self) -> ToolResult:
        self.started = True
        await asyncio.sleep(1)
        return ToolResult(content="too late")


class _SlowButAllowedTool(Tool):
    name = "slow_allowed"
    description = "Sleep longer than global timeout but shorter than tool override."

    def __init__(self) -> None:
        self.started = False

    def timeout_override_seconds(self) -> float | None:
        return 0.1

    async def execute(self) -> ToolResult:
        self.started = True
        await asyncio.sleep(0.03)
        return ToolResult(content="slow but allowed")


class _ToolLoopLLMClient(LLMClient):
    """第一轮请求工具，第二轮根据工具结果返回最终结论。"""

    def __init__(self) -> None:
        """初始化模型请求记录。"""
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """按请求轮次返回 Tool Call 或最终文本。"""
        self.requests.append(request)
        if len(self.requests) == 1:
            assert request.tools[0]["name"] == "echo"
            return LLMResponse(
                content="",
                model="provider-model-id",
                provider="deepseek",
                finish_reason="tool_calls",
                tool_calls=[
                    LLMToolCall(
                        id="call-echo-1",
                        name="echo",
                        arguments={"value": "hello"},
                    )
                ],
            )
        return LLMResponse(
            content="工具返回了 echoed: hello",
            model="provider-model-id",
            provider="deepseek",
            finish_reason="stop",
        )


class _TimeoutToolLoopLLMClient(LLMClient):
    """第一轮请求慢工具，第二轮根据 timeout tool message 返回替代方案。"""

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            assert request.tools[0]["name"] == "slow"
            return LLMResponse(
                content="",
                model="provider-model-id",
                provider="deepseek",
                finish_reason="tool_calls",
                tool_calls=[LLMToolCall(id="call-slow-1", name="slow", arguments={})],
            )
        assert "Tool call timed out after" in request.messages[-1].content
        return LLMResponse(
            content="工具超时，改用替代方案",
            model="provider-model-id",
            provider="deepseek",
            finish_reason="stop",
        )


class _TimeoutOverrideToolLoopLLMClient(LLMClient):
    """第一轮请求慢工具，第二轮根据成功 tool message 返回最终答案。"""

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            assert request.tools[0]["name"] == "slow_allowed"
            return LLMResponse(
                content="",
                model="provider-model-id",
                provider="deepseek",
                finish_reason="tool_calls",
                tool_calls=[LLMToolCall(id="call-slow-allowed-1", name="slow_allowed", arguments={})],
            )
        assert request.messages[-1].content == "slow but allowed"
        return LLMResponse(
            content="工具完成",
            model="provider-model-id",
            provider="deepseek",
            finish_reason="stop",
        )
