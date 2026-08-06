"""Provider for deployed HTTP model proxy endpoints."""

from __future__ import annotations

from typing import Any
import json
import httpx

from bamboo.llms.base import (
    LLMClient,
    LLMContextLengthError,
    LLMRequest,
    LLMRequestError,
    LLMResponse,
    LLMResponseError,
    classify_http_error,
    classify_transport_error,
)
from bamboo.llms.config import ModelConfig, ModelConfigError
from bamboo.llms.media import to_openai_image_url
from bamboo.llms.providers.openai_compatible import _parse_tool_calls


class HttpProviderClient(LLMClient):
    """Adapt Bamboo requests to the deployed HTTP proxy used by prod_check_agent."""

    provider_name = "http_provider"

    def __init__(self, config: ModelConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if config.provider != self.provider_name:
            raise ModelConfigError(
                f"{type(self).__name__} requires provider '{self.provider_name}', got '{config.provider}'"
            )
        self.config = config
        self.transport = transport

    async def complete(self, request: LLMRequest) -> LLMResponse:
        url = self._base_url()
        payload = self._build_payload(request)

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout, transport=self.transport) as client:
                response = await client.post(url, headers=self._headers(), json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _response_error_detail(exc.response)
            error_type, retryable = classify_http_error(exc.response.status_code, detail)
            if error_type == "context_length":
                raise LLMContextLengthError(
                    f"{self.config.provider} request failed with HTTP {exc.response.status_code}: {detail}"
                ) from exc
            raise LLMRequestError(
                f"{self.config.provider} request failed with HTTP {exc.response.status_code}: {detail}",
                error_type=error_type,
                retryable=retryable,
            ) from exc
        except httpx.HTTPError as exc:
            error_type, retryable = classify_transport_error(exc)
            raise LLMRequestError(
                f"{self.config.provider} request failed: {exc}",
                error_type=error_type,
                retryable=retryable,
            ) from exc

        return self._parse_response(response)

    def _base_url(self) -> str:
        if not self.config.base_url:
            raise LLMRequestError(f"No base_url configured for provider '{self.config.provider}'")
        return self.config.base_url

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }
        if self.config.api_key:
            headers.setdefault("Authorization", f"Bearer {self.config.api_key}")
        return headers

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        request_overrides = self.config.extra_body.get("request", {})
        if not isinstance(request_overrides, dict):
            raise ModelConfigError(f"models.{self.config.name}.extra_body.request must be a mapping")

        request_body: dict[str, Any] = {
            "max_completion_tokens": self.config.max_tokens,
            "messages": _serialize_messages(request),
            **request_overrides,
        }
        if self.config.temperature is not None:
            request_body["temperature"] = self.config.temperature
        if request.tools:
            request_body["tools"] = [
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

        payload = {
            "model": _normalize_model_name(self.config.model),
            "request": request_body,
            "timeout": int(self.config.extra_body.get("timeout", 30)),
        }
        for key, value in self.config.extra_body.items():
            if key not in {"request", "timeout"}:
                payload[key] = value
        return payload

    def _parse_response(self, response: httpx.Response) -> LLMResponse:
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMResponseError(f"{self.config.provider} returned non-JSON response") from exc

        if isinstance(data, dict) and not _is_success_response(data):
            detail = _business_error_detail(data)
            raise LLMRequestError(
                f"{self.config.provider} request failed: {detail}",
                error_type="request",
                retryable=False,
            )

        result = data.get("result") if isinstance(data, dict) else None
        completion = result if isinstance(result, dict) else data
        if not isinstance(completion, dict):
            raise LLMResponseError(f"{self.config.provider} returned an invalid response")

        try:
            choice = completion["choices"][0]
            message = choice["message"]
            content = _normalize_content(message.get("content"))
            tool_calls = _parse_tool_calls(message.get("tool_calls", []))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMResponseError(f"{self.config.provider} returned an invalid chat completion response") from exc

        if not content and not tool_calls:
            raise LLMResponseError(f"{self.config.provider} returned an empty response")

        usage = completion.get("usage", {})
        normalized_usage = (
            {key: value for key, value in usage.items() if isinstance(key, str) and isinstance(value, int)}
            if isinstance(usage, dict)
            else {}
        )
        return LLMResponse(
            content=content,
            model=str(completion.get("model") or _normalize_model_name(self.config.model)),
            provider=self.config.provider,
            finish_reason=str(choice.get("finish_reason") or ""),
            tool_calls=tool_calls,
            usage=normalized_usage,
            raw_response=data,
        )


def _serialize_messages(request: LLMRequest) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": [{"type": "text", "text": request.system_prompt}]})
    for message in request.messages:
        if message.role == "tool":
            messages.append(
                {
                    "role": "tool",
                    "content": [{"type": "text", "text": message.content}],
                    "tool_call_id": message.tool_call_id,
                }
            )
            continue
        serialized: dict[str, Any] = {
            "role": message.role,
            "content": _serialize_content_blocks(message.content, message.images),
        }
        if message.tool_calls:
            serialized["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {"name": tool_call.name, "arguments": json.dumps(tool_call.arguments)},
                }
                for tool_call in message.tool_calls
            ]
        messages.append(serialized)
    return messages


def _serialize_content_blocks(content: str, images: list[Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if content:
        blocks.append({"type": "text", "text": content})
    blocks.extend(to_openai_image_url(image) for image in images)
    return blocks


def _normalize_model_name(model: str) -> str:
    return model.removeprefix("local_")


def _is_success_response(data: dict[str, Any]) -> bool:
    if data.get("success") is True:
        return True
    if data.get("code") == 200:
        return True
    return "success" not in data and "code" not in data and "errorCode" not in data


def _business_error_detail(data: dict[str, Any]) -> str:
    for key in ("errorMsg", "error_msg", "message", "msg"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value[:500]
    return str(data)[:500]


def _normalize_content(content: Any) -> str:
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
    try:
        data = response.json()
    except ValueError:
        return response.text[:500] or response.reason_phrase
    if isinstance(data, dict):
        return _business_error_detail(data)
    return str(data)[:500]
