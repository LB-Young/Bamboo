"""实现 MiniMax 模型平台的独立 Provider。"""

from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class MiniMaxClient(OpenAICompatibleClient):
    """调用 MiniMax，并为平台差异保留独立扩展边界。"""

    provider_name = "minimax"
    default_base_url = "https://api.minimax.io/v1"
