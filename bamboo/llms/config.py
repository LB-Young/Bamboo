"""解析并校验 models.yaml 中的模型注册信息。"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

SUPPORTED_PROVIDERS = frozenset({"deepseek", "minimax", "gpt", "claude", "ollama", "vllm"})
API_KEY_OPTIONAL_PROVIDERS = frozenset({"ollama", "vllm"})
_ENV_REFERENCE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class ModelConfigError(ValueError):
    """表示 models.yaml 缺少字段或包含非法模型配置。"""


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """保存一个模型名对应的平台连接参数和生成参数。"""

    name: str
    provider: str
    model: str
    api_key: str = field(repr=False)
    base_url: str = ""
    timeout: float = 60.0
    temperature: float | None = None
    context_window: int = 128000
    max_tokens: int = 4096
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)

    def resolve_environment(self) -> ModelConfig:
        """解析当前模型配置中的环境变量引用，不影响其他未使用模型。"""
        if not self.api_key and self.provider not in API_KEY_OPTIONAL_PROVIDERS:
            raise ModelConfigError(
                f"models.{self.name}.api_key is empty; configure the key before using this model"
            )
        resolved_api_key = ""
        if self.api_key:
            resolved_api_key = _resolve_environment_value(self.api_key, f"models.{self.name}.api_key")
        return replace(
            self,
            api_key=resolved_api_key,
            base_url=_resolve_environment_value(self.base_url, f"models.{self.name}.base_url", allow_empty=True),
            extra_headers={
                key: _resolve_environment_value(value, f"models.{self.name}.extra_headers.{key}")
                for key, value in self.extra_headers.items()
            },
        )


@dataclass(frozen=True, slots=True)
class ModelCatalog:
    """保存 models.yaml 注册的全部模型以及默认模型名。"""

    models: dict[str, ModelConfig]
    default_model: str

    @classmethod
    def from_mapping(cls, document: Mapping[str, Any]) -> ModelCatalog:
        """从 YAML 解析后的字典构建并校验模型目录。"""
        raw_models = document.get("models")
        if not isinstance(raw_models, Mapping) or not raw_models:
            raise ModelConfigError("models.yaml must contain a non-empty 'models' mapping")

        models: dict[str, ModelConfig] = {}
        for model_name, raw_config in raw_models.items():
            if not isinstance(model_name, str) or not model_name.strip():
                raise ModelConfigError("Every model registration must have a non-empty name")
            if not isinstance(raw_config, Mapping):
                raise ModelConfigError(f"Model '{model_name}' configuration must be a mapping")
            models[model_name] = _parse_model_config(model_name, raw_config)

        default_model = document.get("default_model", "")
        if not isinstance(default_model, str) or not default_model:
            raise ModelConfigError("models.yaml must define 'default_model'")
        if default_model not in models:
            raise ModelConfigError(f"Default model '{default_model}' is not registered")
        return cls(models=models, default_model=default_model)


def _parse_model_config(name: str, raw_config: Mapping[str, Any]) -> ModelConfig:
    """把一个模型注册项转换为强类型 ModelConfig。"""
    provider = _required_string(raw_config, "provider", name).lower()
    if provider not in SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise ModelConfigError(f"Model '{name}' uses unsupported provider '{provider}'; supported: {supported}")

    model = _required_string(raw_config, "model", name)
    api_key = _optional_string(raw_config, "api_key", name)
    base_url = _optional_string(raw_config, "base_url", name)
    timeout = _positive_number(raw_config.get("timeout", 60.0), f"models.{name}.timeout")
    context_window = _positive_integer(
        raw_config.get("context_window", 128000),
        f"models.{name}.context_window",
    )
    max_tokens = _positive_integer(raw_config.get("max_tokens", 4096), f"models.{name}.max_tokens")
    if max_tokens >= context_window:
        raise ModelConfigError(f"models.{name}.max_tokens must be smaller than context_window")

    temperature_value = raw_config.get("temperature")
    temperature = None
    if temperature_value is not None:
        if isinstance(temperature_value, bool) or not isinstance(temperature_value, (int, float)):
            raise ModelConfigError(f"models.{name}.temperature must be a number")
        temperature = float(temperature_value)

    extra_headers = _string_mapping(raw_config.get("extra_headers", {}), f"models.{name}.extra_headers")
    extra_body = raw_config.get("extra_body", {})
    if not isinstance(extra_body, Mapping):
        raise ModelConfigError(f"models.{name}.extra_body must be a mapping")

    return ModelConfig(
        name=name,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        temperature=temperature,
        context_window=context_window,
        max_tokens=max_tokens,
        extra_headers=extra_headers,
        extra_body=dict(extra_body),
    )


def _required_string(config: Mapping[str, Any], field_name: str, model_name: str) -> str:
    """读取模型配置中的必填非空字符串字段。"""
    value = config.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ModelConfigError(f"models.{model_name}.{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(config: Mapping[str, Any], field_name: str, model_name: str) -> str:
    """读取模型配置中的可选字符串字段。"""
    value = config.get(field_name, "")
    if not isinstance(value, str):
        raise ModelConfigError(f"models.{model_name}.{field_name} must be a string")
    return value.strip()


def _positive_number(value: Any, field_name: str) -> float:
    """校验并返回大于零的浮点配置值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ModelConfigError(f"{field_name} must be greater than zero")
    return float(value)


def _positive_integer(value: Any, field_name: str) -> int:
    """校验并返回大于零的整数配置值。"""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ModelConfigError(f"{field_name} must be a positive integer")
    return value


def _string_mapping(value: Any, field_name: str) -> dict[str, str]:
    """校验请求头等仅允许字符串键值的映射。"""
    if not isinstance(value, Mapping):
        raise ModelConfigError(f"{field_name} must be a mapping")
    if any(not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()):
        raise ModelConfigError(f"{field_name} keys and values must be strings")
    return dict(value)


def _resolve_environment_value(value: str, field_name: str, *, allow_empty: bool = False) -> str:
    """把完整的 `${ENV_NAME}` 引用替换为环境变量值。"""
    if not value and allow_empty:
        return ""
    match = _ENV_REFERENCE.fullmatch(value)
    if match is None:
        return value
    environment_name = match.group(1)
    resolved = os.environ.get(environment_name, "")
    if not resolved:
        raise ModelConfigError(f"Environment variable '{environment_name}' required by {field_name} is not set")
    return resolved
