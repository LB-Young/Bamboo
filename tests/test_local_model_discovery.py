"""Tests for local Ollama/vLLM model discovery."""

from __future__ import annotations

from pathlib import Path

import anyio
import httpx
import yaml
from typer.testing import CliRunner

from bamboo.llms import LLMFactory
from bamboo.llms.local_discovery import LocalDiscoveryResult, OllamaDiscovery, VLLMDiscovery
from bamboo.llms.model_config_writer import ModelConfigWriter, render_models_yaml_snippet
from bamboo.run import app


def test_ollama_discovery_parses_api_tags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://ollama.test/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "qwen2.5:7b",
                        "size": 123,
                        "modified_at": "2026-07-06T00:00:00Z",
                    }
                ]
            },
        )

    result = anyio.run(
        OllamaDiscovery(base_url="http://ollama.test/v1", transport=httpx.MockTransport(handler)).discover
    )

    assert result.ok
    assert result.base_url == "http://ollama.test/v1"
    assert len(result.models) == 1
    assert result.models[0].registration_name == "ollama-qwen2.5-7b"
    assert result.models[0].base_url == "http://ollama.test/v1"
    assert result.models[0].size == 123


def test_vllm_discovery_parses_openai_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://vllm.test/v1/models"
        return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen2.5-7B-Instruct"}]})

    result = anyio.run(VLLMDiscovery(base_url="http://vllm.test", transport=httpx.MockTransport(handler)).discover)

    assert result.ok
    assert result.base_url == "http://vllm.test/v1"
    assert result.models[0].provider == "vllm"
    assert result.models[0].model == "Qwen/Qwen2.5-7B-Instruct"
    assert result.models[0].registration_name == "vllm-qwen-qwen2.5-7b-instruct"


def test_discovery_returns_structured_error_on_network_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("service unavailable", request=request)

    result = anyio.run(OllamaDiscovery(transport=httpx.MockTransport(handler)).discover)

    assert not result.ok
    assert result.models == ()
    assert result.error_type == "ConnectError"
    assert "service unavailable" in result.error


def test_render_models_yaml_snippet_and_writer(tmp_path: Path) -> None:
    result = anyio.run(
        VLLMDiscovery(
            base_url="http://vllm.test/v1",
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"id": "local-model"}]})),
        ).discover
    )
    snippet = render_models_yaml_snippet(result.models)
    assert "vllm-local-model" in snippet
    assert "base_url: http://vllm.test/v1" in snippet

    config_path = tmp_path / "models.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "default_model": "deepseek-chat",
                "models": {
                    "deepseek-chat": {
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "api_key": "",
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    write_result = ModelConfigWriter(config_path).write_discovered(result.models, set_default=False)
    written = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert write_result.added == ("vllm-local-model",)
    assert write_result.backup_path is not None
    assert write_result.backup_path.is_file()
    assert written["default_model"] == "deepseek-chat"
    assert written["models"]["vllm-local-model"]["provider"] == "vllm"


def test_llm_factory_explicit_local_discovery(monkeypatch) -> None:
    factory = LLMFactory.from_mapping(
        {
            "default_model": "ollama-local",
            "models": {
                "ollama-local": {
                    "provider": "ollama",
                    "model": "qwen2.5:7b",
                    "api_key": "",
                }
            },
        }
    )

    class FakeDiscovery:
        async def discover(self):
            return LocalDiscoveryResult(provider="vllm", base_url="http://vllm.test/v1")

    monkeypatch.setattr("bamboo.llms.factory.create_local_discovery", lambda *args, **kwargs: FakeDiscovery())

    async def run_test():
        return await factory.discover_local_models("vllm", base_url="http://vllm.test")

    result = anyio.run(run_test)

    assert result.ok
    assert result.provider == "vllm"


def test_models_discover_cli_prints_results(monkeypatch) -> None:
    async def fake_discover(provider: str, *, base_url: str | None = None, timeout: float = 5.0):
        return await VLLMDiscovery(
            base_url="http://vllm.test",
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"id": "demo"}]})),
        ).discover()

    monkeypatch.setattr("bamboo.adapters.cli.models.discover_local_models", fake_discover)

    result = CliRunner().invoke(app, ["models", "discover", "vllm"])

    assert result.exit_code == 0
    assert "vllm discovery succeeded" in result.output
    assert "vllm-demo" in result.output
    assert "models.yaml snippet" in result.output
