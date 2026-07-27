"""实现 OpenRouter OpenAI-compatible Provider。"""

from __future__ import annotations

import httpx

from bamboo.llms.media_client import (
    MediaClient,
    MediaRequest,
    MediaResponse,
    collect_urls,
    download_urls,
    http_error_message,
    join_url,
    merge_mappings,
    save_base64_images,
)
from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class OpenRouterClient(OpenAICompatibleClient):
    """调用 OpenRouter Chat Completions 接口。"""

    provider_name = "openrouter"
    default_base_url = "https://openrouter.ai/api/v1"


class OpenRouterImagesClient(MediaClient):
    """调用 OpenRouter Images API。"""

    default_base_url = "https://openrouter.ai/api/v1"

    async def generate(self, request: MediaRequest) -> MediaResponse:
        prompt = str(request.input.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")

        endpoint = str(self.config.extra_body.get("endpoint") or "/images").strip()
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            **merge_mappings(self.config.extra_body.get("parameters"), request.parameters),
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout, transport=self.transport) as client:
                response = await client.post(
                    join_url(self.config.base_url or self.default_base_url, endpoint),
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                urls = collect_urls(data)
                saved_paths: list[str] = []
                if request.download:
                    if urls:
                        saved_paths.extend(await download_urls(client, urls, output_dir=request.output_dir))
                    saved_paths.extend(save_base64_images(data, output_dir=request.output_dir))
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(http_error_message(exc.response)) from exc
        except (httpx.HTTPError, ValueError, OSError) as exc:
            raise RuntimeError(f"Media generation request failed: {exc}") from exc

        lines = ["Media generation succeeded."]
        if urls:
            lines.append("Result URLs:")
            lines.extend(f"- {url}" for url in urls)
        if saved_paths:
            lines.append("Saved files:")
            lines.extend(f"- {path}" for path in saved_paths)
        return MediaResponse(content="\n".join(lines), urls=urls, saved_paths=saved_paths)
