"""验证 provider-specific prompt 和模型能力配置。"""

from __future__ import annotations

from pathlib import Path

import pytest

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory, LLMImage, ModelCatalog
from bamboo.llms.media import images_from_text
from bamboo.prompts import read_provider_prompt_sections
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.tools.registry import ToolRegistry
from bamboo.userspace.userspace import ensure_userspace


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """隔离用户空间，避免真实 ~/.bamboo/prompts/provider 影响测试结果。"""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_model_config_parses_prompt_profile_and_capabilities() -> None:
    """验证 models.yaml 能声明 prompt_profile 和 capabilities。"""
    catalog = ModelCatalog.from_mapping(_model_document(tool_calling=False))
    config = catalog.models["agent-model"]

    assert config.prompt_profile == "ollama"
    assert config.model_type == "text"
    assert config.capabilities.tool_calling is False
    assert config.capabilities.json_schema is False
    assert config.capabilities.vision is False
    assert config.capabilities.max_parallel_tools == 1


def test_model_config_parses_model_type() -> None:
    """验证 models.yaml 能声明模型类型。"""
    catalog = ModelCatalog.from_mapping(_model_document(provider="kimi", prompt_profile="kimi", model_type="vision"))
    config = catalog.models["agent-model"]

    assert config.model_type == "vision"


def test_model_config_parses_media_model_type() -> None:
    """验证 models.yaml 能注册平台无关的媒体模型类型。"""
    catalog = ModelCatalog.from_mapping(
        _model_document(provider="generic_http", prompt_profile="aliyun", model_type="image_generation")
    )
    config = catalog.models["agent-model"]

    assert config.provider == "generic_http"
    assert config.model_type == "image_generation"


def test_aliyun_provider_prompt_is_available() -> None:
    """验证 Aliyun provider prompt 能按 prompt_profile 加载。"""
    sections = read_provider_prompt_sections("aliyun")

    assert any("Aliyun Provider Notes" in section for section in sections)


def test_provider_prompt_sections_can_be_overridden_in_userspace() -> None:
    """验证 provider prompt 从用户空间读取，修改后下一轮读取立即生效。"""
    layout = ensure_userspace()
    provider_prompt = layout.root / "prompts" / "provider" / "deepseek" / "10-tool-calling.md"
    assert provider_prompt.is_file()
    assert "DeepSeek Provider Notes" in "\n".join(read_provider_prompt_sections("deepseek"))

    provider_prompt.write_text("# Custom DeepSeek Provider\n\n用户自定义 provider prompt。", encoding="utf-8")

    sections = read_provider_prompt_sections("deepseek")
    assert sections == ["# Custom DeepSeek Provider\n\n用户自定义 provider prompt。"]


def test_runtime_prompt_includes_active_provider_prompt(tmp_path: Path) -> None:
    """验证 RuntimeContextBuilder 会把当前主模型的 provider prompt 注入请求。"""
    factory = LLMFactory.from_mapping(_model_document(provider="deepseek", prompt_profile="deepseek"))
    task = TaskFactory(config=_StubBambooConfig(_model_document())).create(
        RunParams(
            message="hello",
            project=str(tmp_path),
            session_mode=SessionMode.chat,
            model="agent-model",
        )
    )

    runtime_context = RuntimeContextBuilder(event_bus=EventBus(), llm_factory=factory).build(task)
    prompt = runtime_context.prompt_builder.build(task.session).to_llm_request()

    assert "# Provider Prompt" in prompt.system_prompt
    assert "DeepSeek Provider Notes" in prompt.system_prompt
    assert "Tool Calling: enabled" in prompt.system_prompt
    assert prompt.tools


def test_runtime_prompt_carries_user_images(tmp_path: Path) -> None:
    """验证用户图片输入能进入 LLMRequest。"""
    document = _model_document(provider="kimi", prompt_profile="kimi", model_type="vision")
    document["models"]["agent-model"]["capabilities"]["vision"] = True
    factory = LLMFactory.from_mapping(document)
    task = TaskFactory(config=_StubBambooConfig(document)).create(
        RunParams(
            message="what is in this image?",
            images=[LLMImage(source=str(tmp_path / "image.png"), media_type="image/png")],
            project=str(tmp_path),
            session_mode=SessionMode.chat,
            model="agent-model",
        )
    )

    runtime_context = RuntimeContextBuilder(event_bus=EventBus(), llm_factory=factory).build(task)
    request = runtime_context.prompt_builder.build(task.session).to_llm_request()

    assert request.messages[-1].images[0].media_type == "image/png"


def test_run_params_extracts_image_path_from_text() -> None:
    """验证用户把图片路径直接写在问题里时会自动作为图片输入。"""
    path = "/Users/liubaoyang/Documents/windows/something/1.jpg"
    params = RunParams(message=f"你帮我看一下{path}图片的内容")

    assert params.images[0].source == path
    assert params.images[0].media_type == "image/jpeg"


def test_images_from_text_extracts_http_image_url() -> None:
    """验证文本中的图片 URL 也会被识别。"""
    images = images_from_text("look at https://example.com/a/1.webp?x=1")

    assert images[0].source == "https://example.com/a/1.webp?x=1"


def test_images_from_text_stops_before_escaped_newline_marker() -> None:
    """验证工具结果 JSON 里的 \\nSaved 不会被当作 URL query 的一部分。"""
    images = images_from_text("Result URLs:\\n- https://example.com/a/1.webp?x=1\\nSaved files:")

    assert images[0].source == "https://example.com/a/1.webp?x=1"


def test_images_from_text_does_not_duplicate_url_as_absolute_path() -> None:
    """验证 HTTP URL 不会被绝对路径规则重复识别。"""
    images = images_from_text("look at https://example.com/a/1.webp")

    assert [image.source for image in images] == ["https://example.com/a/1.webp"]


def test_mimo_provider_prompt_is_available() -> None:
    """验证 MiMo provider prompt 能按 prompt_profile 加载。"""
    sections = read_provider_prompt_sections("mimo")

    assert any("MiMo Provider Notes" in section for section in sections)


def test_kimi_provider_prompt_is_available() -> None:
    """验证 Kimi provider prompt 能按 prompt_profile 加载。"""
    sections = read_provider_prompt_sections("kimi")

    assert any("Kimi Provider Notes" in section for section in sections)


def test_tool_calling_disabled_hides_structured_tools(tmp_path: Path) -> None:
    """验证不支持 tool calling 的模型走文本协议 fallback，不发送 tools schema。"""
    document = _model_document(provider="ollama", prompt_profile="ollama", tool_calling=False)
    factory = LLMFactory.from_mapping(document)
    tool_registry = ToolRegistry()
    tool_registry.register(_EchoTool(), source="test")
    task = TaskFactory(config=_StubBambooConfig(document)).create(
        RunParams(
            message="hello",
            project=str(tmp_path),
            session_mode=SessionMode.chat,
            model="agent-model",
        )
    )

    runtime_context = RuntimeContextBuilder(
        event_bus=EventBus(),
        llm_factory=factory,
        tool_registry=tool_registry,
    ).build(task)
    prompt = runtime_context.prompt_builder.build(task.session).to_llm_request()

    assert prompt.tools == []
    assert "Ollama Provider Notes" in prompt.system_prompt
    assert "# Available Tools" not in prompt.system_prompt
    assert "Tool Calling: disabled" in prompt.system_prompt
    assert "Do not claim to call tools" in prompt.system_prompt


def _model_document(
    *,
    provider: str = "ollama",
    prompt_profile: str = "ollama",
    tool_calling: bool = True,
    model_type: str = "text",
) -> dict:
    """创建单模型测试配置。"""
    return {
        "default_model": "agent-model",
        "models": {
            "agent-model": {
                "provider": provider,
                "model": "provider-model-id",
                "model_type": model_type,
                "api_key": "" if provider in {"ollama", "vllm"} else "test-api-key",
                "base_url": "http://localhost:11434/v1" if provider == "ollama" else "https://llm.test/v1",
                "prompt_profile": prompt_profile,
                "max_tokens": 128,
                "capabilities": {
                    "tool_calling": tool_calling,
                    "json_schema": False,
                    "vision": False,
                    "max_parallel_tools": 1,
                },
            }
        },
    }


class _StubBambooConfig:
    """为 TaskFactory 测试提供内存配置。"""

    def __init__(self, models_document: dict) -> None:
        self.models_document = models_document

    def get(self, name: str, default: object = None) -> object:
        if name == "models":
            return self.models_document
        return default


class _EchoTool(Tool):
    """测试用工具。"""

    name = "echo"
    description = "Echo a string value."

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        }

    async def execute(self, value: str) -> ToolResult:
        return ToolResult(content=value)
