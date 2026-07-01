"""实现本地 vLLM OpenAI-compatible 模型 Provider。"""

from bamboo.llms.providers.openai_compatible import OpenAICompatibleClient


class VLLMClient(OpenAICompatibleClient):
    """调用 vLLM OpenAI-compatible Chat Completions 接口。"""

    provider_name = "vllm"
    default_base_url = "http://localhost:8000/v1"
