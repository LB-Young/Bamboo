"""实现 Anthropic Claude 模型平台的独立 Provider。"""

from bamboo.llms.config import ModelConfig, ModelConfigError
from bamboo.llms.providers.anthropic import AnthropicMessagesClient


class ClaudeClient(AnthropicMessagesClient):
    """调用 Claude，并为 Anthropic 平台变化保留独立扩展边界。"""

    provider_name = "claude"

    def __init__(self, config: ModelConfig, **kwargs: object) -> None:
        """校验 Claude Provider 配置后初始化 Messages API 客户端。"""
        if config.provider != self.provider_name:
            raise ModelConfigError(
                f"{type(self).__name__} requires provider '{self.provider_name}', got '{config.provider}'"
            )
        super().__init__(config, **kwargs)
