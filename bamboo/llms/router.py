"""模型路由和一次性 fallback 策略。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from bamboo.llms.base import LLMClient, LLMError
from bamboo.llms.config import ModelConfig
from bamboo.llms.factory import LLMFactory


@dataclass(slots=True)
class LLMRoute:
    """记录某类模型任务的主模型、fallback 模型和当前切换状态。"""

    role: str
    model_name: str
    fallback_model_name: str = ""
    fallback_used: bool = False

    @property
    def active_model_name(self) -> str:
        """返回当前实际应该调用的模型名。"""
        if self.fallback_used and self.fallback_model_name:
            return self.fallback_model_name
        return self.model_name


class LLMRouter:
    """集中处理主模型、辅助模型和 fallback 模型解析。"""

    def __init__(self, llm_factory: LLMFactory, *, config: Mapping[str, Any] | None = None) -> None:
        """保存模型工厂和运行配置。"""
        self.llm_factory = llm_factory
        self.config = config or {}

    def main_route(self, model_name: str, *, fallback_model_name: str = "") -> LLMRoute:
        """创建主 Agent 模型路由。"""
        return LLMRoute(
            role="main",
            model_name=model_name,
            fallback_model_name=self._valid_model_name(fallback_model_name),
        )

    def auxiliary_route(
        self,
        role: str,
        *,
        model_name: str,
        fallback_model_name: str = "",
    ) -> LLMRoute:
        """创建 compaction、memory 等辅助任务模型路由。"""
        return LLMRoute(
            role=role,
            model_name=model_name,
            fallback_model_name=self._valid_model_name(fallback_model_name),
        )

    def client_for(self, route: LLMRoute) -> LLMClient:
        """返回路由当前激活模型的客户端。"""
        return self.llm_factory.get_client(route.active_model_name)

    def config_for(self, route: LLMRoute) -> ModelConfig:
        """返回路由当前激活模型的注册配置。"""
        return self.llm_factory.get_model_config(route.active_model_name)

    def can_fallback(self, route: LLMRoute, exc: Exception) -> bool:
        """判断给定异常是否允许当前 route 切换一次 fallback。"""
        return (
            isinstance(exc, LLMError)
            and exc.retryable
            and bool(route.fallback_model_name)
            and not route.fallback_used
        )

    def activate_fallback(self, route: LLMRoute) -> str:
        """把 route 切到 fallback 模型并返回新的激活模型名。"""
        if not route.fallback_model_name:
            raise ValueError(f"Route '{route.role}' does not have fallback_model_name configured")
        route.fallback_used = True
        return route.active_model_name

    def _valid_model_name(self, model_name: str) -> str:
        """只接受已注册模型名，空值或未知值视为未配置。"""
        if model_name and self.llm_factory.has_model(model_name):
            return model_name
        return ""

