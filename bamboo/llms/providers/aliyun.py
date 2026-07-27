"""实现阿里云百炼 / DashScope 文本模型 Provider。"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from bamboo.llms.media_client import (
    MediaClient,
    MediaRequest,
    MediaResponse,
    apply_input_field_mapping,
    collect_urls,
    download_urls,
    http_error_message,
    join_url,
    merge_mappings,
    nested_get,
    redact_response,
)
from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class AliyunClient(OpenAICompatibleClient):
    """调用阿里云百炼 OpenAI-compatible Chat Completions 接口。"""

    provider_name = "aliyun"
    default_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class DashScopeAsyncMediaClient(MediaClient):
    """调用 DashScope 异步媒体任务接口。"""

    default_base_url = "https://dashscope.aliyuncs.com/api/v1"

    async def generate(self, request: MediaRequest) -> MediaResponse:
        endpoint = str(self.config.extra_body.get("endpoint") or "").strip()
        if not endpoint:
            raise ValueError(f"{self.config.name} does not configure an endpoint")

        payload = {
            "model": self.config.model,
            "input": apply_input_field_mapping(request.input, self.config.extra_body.get("input_fields")),
        }
        effective_parameters = merge_mappings(self.config.extra_body.get("parameters"), request.parameters)
        if effective_parameters:
            payload["parameters"] = effective_parameters

        base_url = (self.config.base_url or self.default_base_url).rstrip("/")
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
            **self.config.extra_headers,
        }

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout, transport=self.transport) as client:
                create_response = await client.post(join_url(base_url, endpoint), headers=headers, json=payload)
                create_response.raise_for_status()
                create_data = create_response.json()
                task_id = _extract_task_id(create_data)
                if not task_id:
                    return MediaResponse(
                        content="",
                        status="FAILED",
                        metadata={"response": redact_response(create_data)},
                    )

                final_data: dict[str, Any] = create_data
                status = str(nested_get(final_data, ("output", "task_status")) or "").upper()
                while status not in {"SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"}:
                    if time.monotonic() - started > request.timeout_seconds:
                        return MediaResponse(
                            content=f"Media task {task_id} is still {status or 'PENDING'} after timeout.",
                            task_id=task_id,
                            status=status or "PENDING",
                            metadata={"task_id": task_id, "status": status or "PENDING"},
                        )
                    await asyncio.sleep(request.poll_interval_seconds)
                    poll_response = await client.get(join_url(base_url, f"/tasks/{task_id}"), headers=headers)
                    poll_response.raise_for_status()
                    final_data = poll_response.json()
                    status = str(nested_get(final_data, ("output", "task_status")) or "").upper()

                if status != "SUCCEEDED":
                    return MediaResponse(
                        content=_task_error_message(final_data) or f"Media task {task_id} ended with {status}",
                        task_id=task_id,
                        status=status,
                        metadata={"task_id": task_id, "status": status, "response": redact_response(final_data)},
                    )

                urls = collect_urls(final_data)
                saved_paths = await download_urls(client, urls, output_dir=request.output_dir) if request.download and urls else []
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(http_error_message(exc.response)) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f"Media generation request failed: {exc}") from exc

        lines = [f"Media task {task_id} succeeded."]
        if urls:
            lines.append("Result URLs:")
            lines.extend(f"- {url}" for url in urls)
        if saved_paths:
            lines.append("Saved files:")
            lines.extend(f"- {path}" for path in saved_paths)
        return MediaResponse(
            content="\n".join(lines),
            urls=urls,
            saved_paths=saved_paths,
            task_id=task_id,
            metadata={"task_id": task_id, "status": "SUCCEEDED", "response": redact_response(final_data)},
        )


def _extract_task_id(data: dict[str, Any]) -> str:
    value = nested_get(data, ("output", "task_id"))
    return value if isinstance(value, str) else ""


def _task_error_message(data: dict[str, Any]) -> str:
    output = data.get("output")
    if isinstance(output, dict):
        for key in ("message", "code", "task_status"):
            value = output.get(key)
            if isinstance(value, str) and value:
                return value
    return ""
