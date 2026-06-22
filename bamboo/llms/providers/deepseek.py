"""实现 DeepSeek 模型平台的独立 Provider。"""

from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class DeepSeekClient(OpenAICompatibleClient):
    """调用 DeepSeek，并为平台差异保留独立扩展边界。"""

    provider_name = "deepseek"
    default_base_url = "https://api.deepseek.com/v1"
