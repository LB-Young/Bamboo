"""Verify generic media tools use configured model protocols."""

from __future__ import annotations

import json
import base64
from pathlib import Path

import anyio
import httpx

from bamboo.tools.buildin.media_generation import ImageEditTool, TextToImageTool, TextToVideoTool


def test_text_to_image_tool_submits_and_polls_task(tmp_path: Path) -> None:
    """验证文生图工具按 tools.yaml 选择模型并保存结果。"""
    requests: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else {}
        requests.append((request.method, str(request.url), payload))
        if request.method == "POST":
            assert request.headers["authorization"] == "Bearer test-key"
            assert request.headers["x-dashscope-async"] == "enable"
            assert payload["model"] == "wanx2.1-t2i-turbo"
            assert payload["input"] == {"prompt": "green bamboo logo"}
            assert payload["parameters"]["size"] == "512*512"
            return httpx.Response(200, json={"output": {"task_id": "task-1", "task_status": "PENDING"}})
        if str(request.url).endswith("/tasks/task-1"):
            return httpx.Response(
                200,
                json={"output": {"task_id": "task-1", "task_status": "SUCCEEDED", "results": [{"url": "https://asset.test/a.png"}]}},
            )
        if str(request.url) == "https://asset.test/a.png":
            return httpx.Response(200, content=b"png-bytes", headers={"content-type": "image/png"})
        return httpx.Response(404)

    async def run_test() -> None:
        tool = TextToImageTool(
            config_document=_models_document(),
            tools_document=_tools_document(output_dir=str(tmp_path)),
            transport=httpx.MockTransport(handler),
        )
        result = await tool.execute(prompt="green bamboo logo", size="512*512")

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata["task_id"] == "task-1"
        assert result.metadata["urls"] == ["https://asset.test/a.png"]
        assert Path(result.metadata["saved_paths"][0]).read_bytes() == b"png-bytes"

    anyio.run(run_test)
    assert [item[0] for item in requests] == ["POST", "GET", "GET"]


def test_text_to_image_tool_supports_openrouter_images_protocol(tmp_path: Path) -> None:
    """验证 OpenRouter 图片协议使用 /images 并保存 b64_json。"""
    png_bytes = b"\x89PNG\r\n\x1a\n"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.method == "POST"
        assert str(request.url) == "https://openrouter.test/api/v1/images"
        assert request.headers["authorization"] == "Bearer test-key"
        assert payload == {
            "model": "openai/gpt-5-image-mini",
            "prompt": "tiny bamboo icon",
            "n": 1,
            "size": "1024x1024",
        }
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(png_bytes).decode("ascii"), "media_type": "image/png"}]},
        )

    async def run_test() -> None:
        tool = TextToImageTool(
            config_document=_models_document(),
            tools_document={"media_generation": {"text_to_image_model": "openrouter-image", "output_dir": str(tmp_path)}},
            transport=httpx.MockTransport(handler),
        )
        result = await tool.execute(prompt="tiny bamboo icon", size="1024x1024")

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata["urls"] == []
        assert Path(result.metadata["saved_paths"][0]).read_bytes() == png_bytes

    anyio.run(run_test)


def test_text_to_video_tool_rejects_wrong_model_type() -> None:
    """验证工具只能使用对应的媒体模型类型。"""

    async def run_test() -> None:
        tool = TextToVideoTool(
            config_document=_models_document(),
            tools_document={"media_generation": {"text_to_video_model": "aliyun-t2i"}},
            transport=httpx.MockTransport(lambda request: httpx.Response(500)),
        )
        result = await tool.execute(prompt="moving bamboo")

        assert result.success is False
        assert "must use model_type 'video_generation'" in result.error

    anyio.run(run_test)


def test_media_tool_exposes_timeout_override_from_tools_config() -> None:
    """验证媒体工具可用 tools.yaml 放开 runtime tool-call 超时。"""
    tool = TextToImageTool(tools_document={"media_generation": {"tool_call_timeout_seconds": 900}})

    assert tool.timeout_override_seconds() == 900


def test_image_edit_tool_uses_base_image_url() -> None:
    """验证图片编辑工具按 DashScope API 使用 base_image_url。"""
    posted_payload: dict | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posted_payload
        if request.method == "POST":
            posted_payload = json.loads(request.content)
            return httpx.Response(200, json={"output": {"task_id": "task-edit", "task_status": "SUCCEEDED", "results": []}})
        return httpx.Response(404)

    async def run_test() -> None:
        tool = ImageEditTool(
            config_document=_models_document(),
            tools_document={"media_generation": {"image_edit_model": "aliyun-edit", "poll_interval_seconds": 0.001}},
            transport=httpx.MockTransport(handler),
        )
        result = await tool.execute(prompt="make it brighter", image_url="https://asset.test/source.png", download=False)

        assert result.success is True
        assert posted_payload is not None
        assert posted_payload["input"] == {
            "function": "description_edit",
            "prompt": "make it brighter",
            "base_image_url": "https://asset.test/source.png",
        }

    anyio.run(run_test)


def _tools_document(*, output_dir: str) -> dict:
    return {
        "media_generation": {
            "text_to_image_model": "aliyun-t2i",
            "text_to_video_model": "aliyun-t2v",
            "output_dir": output_dir,
            "poll_interval_seconds": 0.001,
            "timeout_seconds": 1,
        }
    }


def _models_document() -> dict:
    return {
        "default_model": "aliyun-chat",
        "models": {
            "aliyun-chat": {
                "provider": "aliyun",
                "model": "qwen-plus",
                "model_type": "text",
                "api_key": "test-key",
                "base_url": "https://dashscope.test/compatible-mode/v1",
                "max_tokens": 128,
            },
            "aliyun-t2i": {
                "provider": "generic_http",
                "model": "wanx2.1-t2i-turbo",
                "model_type": "image_generation",
                "api_key": "test-key",
                "base_url": "https://dashscope.test/api/v1",
                "max_tokens": 128,
                "extra_body": {
                    "protocol": "dashscope_async",
                    "endpoint": "/services/aigc/text2image/image-synthesis",
                    "parameters": {"size": "1024*1024"},
                },
            },
            "aliyun-t2v": {
                "provider": "aliyun",
                "model": "wan2.7-t2v-2026-06-12",
                "model_type": "video_generation",
                "api_key": "test-key",
                "base_url": "https://dashscope.test/api/v1",
                "max_tokens": 128,
                "extra_body": {
                    "protocol": "dashscope_async",
                    "endpoint": "/services/aigc/video-generation/video-synthesis",
                },
            },
            "aliyun-edit": {
                "provider": "aliyun",
                "model": "wanx2.1-imageedit",
                "model_type": "image_edit",
                "api_key": "test-key",
                "base_url": "https://dashscope.test/api/v1",
                "max_tokens": 128,
                "extra_body": {
                    "protocol": "dashscope_async",
                    "endpoint": "/services/aigc/image2image/image-synthesis",
                    "input_fields": {"image_url": "base_image_url"},
                },
            },
            "openrouter-image": {
                "provider": "openrouter",
                "model": "openai/gpt-5-image-mini",
                "model_type": "image_generation",
                "api_key": "test-key",
                "base_url": "https://openrouter.test/api/v1",
                "max_tokens": 128,
                "extra_body": {
                    "protocol": "openrouter_images",
                    "endpoint": "/images",
                    "parameters": {"n": 1},
                },
            },
        },
    }
