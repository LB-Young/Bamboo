"""实现 Kimi OpenAI-compatible 模型 Provider。"""

from typing import Any

from bamboo.llms.base import LLMRequest
from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class KimiClient(OpenAICompatibleClient):
    """调用 Kimi 的 OpenAI-compatible Chat Completions 接口。"""

    provider_name = "kimi"
    default_base_url = "https://api.moonshot.cn/v1"

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """Kimi K3 requires top-level reasoning_effort=max."""
        payload = super()._build_payload(request)
        if self.config.model == "kimi-k3":
            payload.setdefault("reasoning_effort", "max")
        return payload
