"""实现 OpenAI GPT 模型平台的独立 Provider。"""

from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class GPTClient(OpenAICompatibleClient):
    """调用 OpenAI GPT，并为平台差异保留独立扩展边界。"""

    provider_name = "gpt"
    default_base_url = "https://api.openai.com/v1"
