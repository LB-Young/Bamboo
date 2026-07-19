"""根据模型注册名创建并缓存对应平台的 LLM 客户端。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from bamboo.helpers.config import BambooConfig
from bamboo.llms.base import LLMClient
from bamboo.llms.config import ModelCatalog, ModelConfig, ModelConfigError
from bamboo.llms.local_discovery import LocalDiscoveryResult, create_local_discovery
from bamboo.llms.providers import (
    ClaudeClient,
    DeepSeekClient,
    GPTClient,
    KimiClient,
    MiniMaxClient,
    MimoClient,
    OllamaClient,
    VLLMClient,
)

ProviderBuilder = Callable[[ModelConfig], LLMClient]


class LLMFactory:
    """管理模型名注册、Provider 适配器注册和客户端创建。"""

    def __init__(self, catalog: ModelCatalog) -> None:
        """加载模型目录并注册 Bamboo 当前支持的平台。"""
        self._models = dict(catalog.models)
        self._default_model = catalog.default_model
        self._providers: dict[str, ProviderBuilder] = {}
        self._clients: dict[str, LLMClient] = {}
        self.register_provider("gpt", GPTClient)
        self.register_provider("deepseek", DeepSeekClient)
        self.register_provider("kimi", KimiClient)
        self.register_provider("minimax", MiniMaxClient)
        self.register_provider("mimo", MimoClient)
        self.register_provider("claude", ClaudeClient)
        self.register_provider("ollama", OllamaClient)
        self.register_provider("vllm", VLLMClient)

    @classmethod
    def from_mapping(cls, document: Mapping[str, Any]) -> LLMFactory:
        """从 models.yaml 对应的字典创建统一工厂。"""
        return cls(ModelCatalog.from_mapping(document))

    @classmethod
    def from_bamboo_config(cls, bamboo_config: BambooConfig) -> LLMFactory:
        """从启动阶段已经加载的用户 models 配置创建统一工厂。"""
        document = bamboo_config.get("models", {})
        if not isinstance(document, Mapping) or not document.get("models"):
            config_path = BambooConfig.get_configs_dir() / "models.yaml"
            raise ModelConfigError(
                f"Model configuration is empty: {config_path}. "
                "Configure at least one model before starting Bamboo."
            )
        return cls.from_mapping(document)

    @property
    def default_model_name(self) -> str:
        """返回 models.yaml 声明的默认模型注册名。"""
        return self._default_model

    def list_model_names(self) -> list[str]:
        """返回 Agent 当前有权按名称使用的全部已注册模型。"""
        return sorted(self._models)

    def has_model(self, model_name: str) -> bool:
        """判断模型名是否已经在 models.yaml 中注册。"""
        return model_name in self._models

    def get_model_config(self, model_name: str | None = None) -> ModelConfig:
        """返回模型注册配置，供 Runtime 读取上下文窗口等非敏感元数据。"""
        selected_name = model_name or self._default_model
        config = self._models.get(selected_name)
        if config is None:
            available = ", ".join(self.list_model_names()) or "(none)"
            raise ModelConfigError(f"Model '{selected_name}' is not registered; available models: {available}")
        return config

    def register_model(self, config: ModelConfig, *, replace: bool = False) -> None:
        """注册一个模型名，默认拒绝覆盖已有注册以防止权限配置被静默替换。"""
        if config.name in self._models and not replace:
            raise ModelConfigError(f"Model '{config.name}' is already registered")
        self._models[config.name] = config
        self._clients.pop(config.name, None)

    def register_provider(self, provider: str, builder: ProviderBuilder, *, replace: bool = False) -> None:
        """注册 Provider 客户端构造器，供内置实现或测试替换。"""
        normalized_provider = provider.strip().lower()
        if not normalized_provider:
            raise ModelConfigError("Provider name cannot be empty")
        if normalized_provider in self._providers and not replace:
            raise ModelConfigError(f"Provider '{normalized_provider}' is already registered")
        self._providers[normalized_provider] = builder

    def get_client(self, model_name: str | None = None) -> LLMClient:
        """按 Agent 配置的模型名返回缓存客户端，并在首次使用时解析密钥。"""
        selected_name = model_name or self._default_model
        config = self.get_model_config(selected_name)

        cached_client = self._clients.get(selected_name)
        if cached_client is not None:
            return cached_client

        builder = self._providers.get(config.provider)
        if builder is None:
            raise ModelConfigError(f"No LLM provider adapter registered for '{config.provider}'")

        client = builder(config.resolve_environment())
        self._clients[selected_name] = client
        return client

    async def discover_local_models(
        self,
        provider: str,
        *,
        base_url: str | None = None,
        timeout: float = 5.0,
    ) -> LocalDiscoveryResult:
        """Explicitly discover local Ollama/vLLM models without touching runtime startup."""
        return await create_local_discovery(provider, base_url=base_url, timeout=timeout).discover()
