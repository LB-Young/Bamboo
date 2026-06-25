"""提供 Claude Provider 可以继承的 Anthropic Messages 协议基类。"""

from __future__ import annotations

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
from bamboo.llms.config import ModelConfig

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicMessagesClient(LLMClient):
    """封装 Anthropic `/messages` 通用流程，供 Claude Provider 继承。"""

    default_base_url = "https://api.anthropic.com/v1"

    def __init__(self, config: ModelConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        """保存 Claude 模型配置，并允许测试注入 httpx transport。"""
        self.config = config
        self.transport = transport

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """发送 Anthropic Messages 请求并转换为统一响应。"""
        base_url = (self.config.base_url or self.default_base_url).rstrip("/")
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }
        payload = self._build_payload(request)

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout, transport=self.transport) as client:
                response = await client.post(f"{base_url}/messages", headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _response_error_detail(exc.response)
            raise LLMRequestError(f"claude request failed with HTTP {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise LLMRequestError(f"claude request failed: {exc}") from exc

        return self._parse_response(response)

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """把统一请求转换为 Anthropic Messages 请求体。"""
        system_parts = [request.system_prompt] if request.system_prompt else []
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            if message.role == "system":
                system_parts.append(message.content)
                continue
            if message.role == "assistant" and message.tool_calls:
                content_blocks: list[dict[str, Any]] = []
                if message.content:
                    content_blocks.append({"type": "text", "text": message.content})
                content_blocks.extend(
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "input": tool_call.arguments,
                    }
                    for tool_call in message.tool_calls
                )
                _append_message(messages, "assistant", content_blocks)
                continue
            if message.role == "tool":
                _append_message(
                    messages,
                    "user",
                    [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.tool_call_id,
                            "content": message.content,
                        }
                    ],
                )
                continue
            role = "assistant" if message.role == "assistant" else "user"
            _append_message(messages, role, [{"type": "text", "text": message.content}])

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            **self.config.extra_body,
        }
        system_prompt = "\n\n".join(part for part in system_parts if part)
        if system_prompt:
            payload["system"] = system_prompt
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if request.tools:
            payload["tools"] = list(request.tools)
        return payload

    def _parse_response(self, response: httpx.Response) -> LLMResponse:
        """从 Anthropic 响应的 content blocks 中提取所有文本。"""
        try:
            data = response.json()
            content_blocks = data["content"]
            content = "".join(
                block["text"]
                for block in content_blocks
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
            )
            tool_calls = [
                LLMToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=block.get("input", {}),
                )
                for block in content_blocks
                if isinstance(block, dict)
                and block.get("type") == "tool_use"
                and isinstance(block.get("id"), str)
                and isinstance(block.get("name"), str)
                and isinstance(block.get("input", {}), dict)
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMResponseError("claude returned an invalid Messages API response") from exc

        if not content and not tool_calls:
            raise LLMResponseError("claude returned an empty response")

        usage = data.get("usage", {})
        normalized_usage = {
            key: value for key, value in usage.items() if isinstance(key, str) and isinstance(value, int)
        } if isinstance(usage, dict) else {}
        return LLMResponse(
            content=content,
            model=str(data.get("model") or self.config.model),
            provider=self.config.provider,
            finish_reason=str(data.get("stop_reason") or ""),
            tool_calls=tool_calls,
            usage=normalized_usage,
            raw_response=data,
        )


def _append_message(messages: list[dict[str, Any]], role: str, blocks: list[dict[str, Any]]) -> None:
    """追加 Anthropic 消息，并合并连续的同角色 content blocks。"""
    if messages and messages[-1]["role"] == role:
        messages[-1]["content"].extend(blocks)
        return
    messages.append({"role": role, "content": list(blocks)})


def _response_error_detail(response: httpx.Response) -> str:
    """从 Anthropic 错误响应中提取可读且不包含认证头的信息。"""
    try:
        data = response.json()
    except ValueError:
        return response.text[:500] or response.reason_phrase
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"][:500]
    return str(data)[:500]
