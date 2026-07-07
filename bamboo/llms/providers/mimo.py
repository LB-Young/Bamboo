"""实现小米 MiMo OpenAI-compatible 模型 Provider。"""

from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class MimoClient(OpenAICompatibleClient):
    """调用 MiMo 的 OpenAI-compatible Chat Completions 接口。"""

    provider_name = "mimo"
    default_base_url = "https://api.xiaomimimo.com/v1"

    def _headers(self) -> dict[str, str]:
        """MiMo quick-start uses `api-key` instead of Bearer Authorization."""
        headers = {
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }
        if self.config.api_key:
            headers["api-key"] = self.config.api_key
        return headers

    def _max_tokens_field(self) -> str:
        """MiMo quick-start documents `max_completion_tokens`."""
        return "max_completion_tokens"
