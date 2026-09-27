"""Implement the Zhipu GLM OpenAI-compatible provider."""

from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class ZhipuClient(OpenAICompatibleClient):
    """Call Zhipu GLM through its OpenAI-compatible Chat Completions endpoint."""

    provider_name = "zhipu"
    default_base_url = "https://open.bigmodel.cn/api/paas/v4"
