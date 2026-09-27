import json

import httpx
import pytest

from bamboo.llms.base import LLMMessage, LLMRequest
from bamboo.llms.config import ModelCatalog
from bamboo.llms.factory import LLMFactory
from bamboo.llms.providers.zhipu import ZhipuClient


def test_zhipu_provider_is_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIPU_API_KEY", "test-key")
    factory = LLMFactory.from_mapping(
        {
            "default_model": "zhipu-glm",
            "models": {
                "zhipu-glm": {
                    "provider": "zhipu",
                    "model": "glm-5.3-flash",
                    "model_type": "text",
                    "prompt_profile": "gpt",
                    "api_key": "${ZHIPU_API_KEY}",
                    "max_tokens": 4096,
                    "context_window": 128000,
                    "capabilities": {"tool_calling": True},
                }
            },
        }
    )

    client = factory.get_client("zhipu-glm")

    assert isinstance(client, ZhipuClient)
    assert client.config.api_key == "test-key"


async def test_zhipu_uses_official_chat_completions_endpoint() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        seen["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "model": "glm-5.3-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello from glm"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            },
        )

    catalog = ModelCatalog.from_mapping(
        {
            "default_model": "zhipu-glm",
            "models": {
                "zhipu-glm": {
                    "provider": "zhipu",
                    "model": "glm-5.3-flash",
                    "model_type": "text",
                    "prompt_profile": "gpt",
                    "api_key": "test-key",
                    "max_tokens": 4096,
                    "context_window": 128000,
                }
            },
        }
    )
    config = catalog.models["zhipu-glm"]
    client = ZhipuClient(config, transport=httpx.MockTransport(handler))

    response = await client.complete(LLMRequest(messages=[LLMMessage(role="user", content="hi")]))

    assert seen["url"] == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    assert seen["authorization"] == "Bearer test-key"
    payload = json.loads(str(seen["payload"]))
    assert payload["model"] == "glm-5.3-flash"
    assert response.content == "hello from glm"
    assert response.provider == "zhipu"
