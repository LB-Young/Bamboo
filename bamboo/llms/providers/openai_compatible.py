"""提供 OpenAI-compatible Provider 可以继承的协议基类。"""

from __future__ import annotations

import json
from typing import Any

import httpx

from bamboo.llms.base import (
    LLMClient,
    LLMRequest,
    LLMRequestError,
    LLMResponse,
    LLMResponseError,
    LLMToolCall,
)
from bamboo.llms.config import ModelConfig, ModelConfigError


class OpenAICompatibleClient(LLMClient):
    """封装 `/chat/completions` 通用流程，供具体平台 Provider 继承。"""

    provider_name = ""
    default_base_url = ""

    def __init__(self, config: ModelConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        """保存模型配置，并允许测试注入 httpx transport。"""
        if self.provider_name and config.provider != self.provider_name:
            raise ModelConfigError(
                f"{type(self).__name__} requires provider '{self.provider_name}', got '{config.provider}'"
            )
        self.config = config
        self.transport = transport

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """发送 Chat Completions 请求并转换为统一响应。"""
        url = f"{self._base_url()}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }
        payload = self._build_payload(request)

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout, transport=self.transport) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _response_error_detail(exc.response)
            raise LLMRequestError(
                f"{self.config.provider} request failed with HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMRequestError(f"{self.config.provider} request failed: {exc}") from exc

        return self._parse_response(response)

    def _base_url(self) -> str:
        """返回配置地址，未配置时使用当前 Provider 的默认地址。"""
        base_url = self.config.base_url or self.default_base_url
        if not base_url:
            raise LLMRequestError(f"No base_url configured for provider '{self.config.provider}'")
        return base_url.rstrip("/")

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """把统一请求转换为 OpenAI Chat Completions 请求体。"""
        messages: list[dict[str, Any]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for message in request.messages:
            if message.role == "assistant" and message.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content or None,
                        "tool_calls": [_serialize_tool_call(tool_call) for tool_call in message.tool_calls],
                    }
                )
                continue
            if message.role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "content": message.content,
                        "tool_call_id": message.tool_call_id,
                    }
                )
                continue
            messages.append({"role": message.role, "content": message.content})

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            **self.config.extra_body,
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                    },
                }
                for tool in request.tools
            ]
        return payload

    def _parse_response(self, response: httpx.Response) -> LLMResponse:
        """从 Chat Completions 响应中提取文本、结束原因和 token 用量。"""
        try:
            data = response.json()
            choice = data["choices"][0]
            response_message = choice["message"]
            content = _normalize_content(response_message.get("content"))
            tool_calls = _parse_tool_calls(response_message.get("tool_calls", []))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMResponseError(f"{self.config.provider} returned an invalid chat completion response") from exc

        if not content and not tool_calls:
            raise LLMResponseError(f"{self.config.provider} returned an empty response")

        usage = data.get("usage", {})
        normalized_usage = {
            key: value for key, value in usage.items() if isinstance(key, str) and isinstance(value, int)
        } if isinstance(usage, dict) else {}
        return LLMResponse(
            content=content,
            model=str(data.get("model") or self.config.model),
            provider=self.config.provider,
            finish_reason=str(choice.get("finish_reason") or ""),
            tool_calls=tool_calls,
            usage=normalized_usage,
            raw_response=data,
        )


def _serialize_tool_call(tool_call: LLMToolCall) -> dict[str, Any]:
    """把统一 Tool Call 转换为 OpenAI assistant tool_call。"""
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.name,
            "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
        },
    }


def _parse_tool_calls(raw_tool_calls: Any) -> list[LLMToolCall]:
    """解析 OpenAI-compatible 响应中的 function tool_calls。"""
    if raw_tool_calls is None:
        return []
    if not isinstance(raw_tool_calls, list):
        raise LLMResponseError("tool_calls must be a list")

    parsed_calls: list[LLMToolCall] = []
    for index, raw_call in enumerate(raw_tool_calls):
        if not isinstance(raw_call, dict) or not isinstance(raw_call.get("function"), dict):
            raise LLMResponseError("tool_call.function must be an object")
        function = raw_call["function"]
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise LLMResponseError("tool_call.function.name must be a non-empty string")
        raw_arguments = function.get("arguments", "{}")
        if isinstance(raw_arguments, str):
            arguments = json.loads(raw_arguments or "{}")
        else:
            arguments = raw_arguments
        if not isinstance(arguments, dict):
            raise LLMResponseError("tool_call.function.arguments must decode to an object")
        call_id = raw_call.get("id")
        parsed_calls.append(
            LLMToolCall(
                id=call_id if isinstance(call_id, str) and call_id else f"tool_call_{index}",
                name=name,
                arguments=arguments,
            )
        )
    return parsed_calls


def _normalize_content(content: Any) -> str:
    """兼容字符串内容和部分平台返回的文本块列表。"""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "".join(parts)


def _response_error_detail(response: httpx.Response) -> str:
    """提取平台错误摘要，同时避免把请求头中的 API Key 写入异常。"""
    try:
        data = response.json()
    except ValueError:
        return response.text[:500] or response.reason_phrase
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"][:500]
        if isinstance(error, str):
            return error[:500]
    return str(data)[:500]
