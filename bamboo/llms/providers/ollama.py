"""实现本地 Ollama OpenAI-compatible 模型 Provider。"""

from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class OllamaClient(OpenAICompatibleClient):
    """调用 Ollama 的 OpenAI-compatible Chat Completions 接口。"""

    provider_name = "ollama"
    default_base_url = "http://localhost:11434/v1"
