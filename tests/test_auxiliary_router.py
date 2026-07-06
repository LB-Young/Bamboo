"""Tests for auxiliary model router expansion."""

from __future__ import annotations

import anyio

from bamboo.factory.event_bus import EventBus
from bamboo.factory.task_factory import TaskFactory
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMClient, LLMFactory, LLMRequest, LLMResponse
from bamboo.llms.base import LLMRequestError
from bamboo.llms.router import LLMRouter
from bamboo.runtime.context_compactor import ContextCompactor
from bamboo.runtime.runtime_context import RuntimeContextBuilder


def test_auxiliary_router_resolves_role_config_and_fallbacks() -> None:
    factory = LLMFactory.from_mapping(_model_document())
    router = LLMRouter(
        factory,
        config={
            "auxiliary_models": {
                "memory": {"model": "memory-model", "fallbacks": ["fallback-model"]},
                "skills_hub": "skills-model",
            }
        },
    )

    memory_route = router.route_for_role("memory", default_model_name="main-model")
    skills_route = router.route_for_role("skills-hub", default_model_name="main-model")
    missing_route = router.route_for_role("web_extract", default_model_name="main-model")

    assert memory_route.model_name == "memory-model"
    assert memory_route.fallback_model_name == "fallback-model"
    assert skills_route.model_name == "skills-model"
    assert missing_route.model_name == "main-model"


def test_auxiliary_routes_keep_independent_fallback_state() -> None:
    factory = LLMFactory.from_mapping(_model_document())
    router = LLMRouter(
        factory,
        config={
            "auxiliary_models": {
                "memory": {"model": "memory-model", "fallbacks": ["fallback-model"]},
                "compaction": {"model": "summary-model", "fallbacks": ["fallback-model"]},
            }
        },
    )
    memory_route = router.route_for_role("memory", default_model_name="main-model")
    compaction_route = router.route_for_role("compaction", default_model_name="main-model")

    router.activate_fallback(memory_route)

    assert memory_route.active_model_name == "fallback-model"
    assert compaction_route.active_model_name == "summary-model"
    assert not compaction_route.fallback_used


def test_runtime_context_exposes_auxiliary_role_clients() -> None:
    document = _model_document()
    config = _StubBambooConfig(
        document,
        agent_document={
            "model": "main-model",
            "auxiliary_models": {
                "memory": {"model": "memory-model", "fallbacks": ["fallback-model"]},
                "compaction": {"model": "summary-model"},
            },
        },
    )
    factory = LLMFactory.from_mapping(document)
    task = TaskFactory(config=config).create(RunParams(message="hello", model="main-model"))
    context = RuntimeContextBuilder(event_bus=EventBus(), llm_factory=factory).build(task)

    assert context.model_name_for_role("memory") == "memory-model"
    assert context.route_for_role("memory").fallback_model_name == "fallback-model"
    assert context.compaction_model_name == "summary-model"
    assert context.model_name_for_role("missing") == "main-model"


def test_compactor_fallback_does_not_change_main_route() -> None:
    factory = LLMFactory.from_mapping(_model_document())
    failing_compaction = _FailingLLMClient()
    fallback_compaction = _StaticLLMClient("short summary")
    factory.register_provider(
        "gpt",
        lambda config: failing_compaction if config.name == "summary-model" else fallback_compaction,
        replace=True,
    )
    router = LLMRouter(
        factory,
        config={"auxiliary_models": {"compaction": {"model": "summary-model", "fallbacks": ["fallback-model"]}}},
    )
    main_route = router.main_route("main-model", fallback_model_name="fallback-model")
    compaction_route = router.route_for_role("compaction", default_model_name="main-model")
    compactor = ContextCompactor(
        llm_client=router.client_for(compaction_route),
        model_config=router.config_for(main_route),
        llm_router=router,
        route=compaction_route,
    )

    async def run_test() -> None:
        response = await compactor._complete_with_fallback("old messages")
        assert response.content == "short summary"

    anyio.run(run_test)

    assert compaction_route.active_model_name == "fallback-model"
    assert main_route.active_model_name == "main-model"
    assert len(failing_compaction.requests) == 1
    assert len(fallback_compaction.requests) == 1


def _model_document() -> dict:
    return {
        "default_model": "main-model",
        "models": {
            "main-model": {"provider": "deepseek", "model": "main", "api_key": "key"},
            "memory-model": {"provider": "deepseek", "model": "memory", "api_key": "key"},
            "skills-model": {"provider": "deepseek", "model": "skills", "api_key": "key"},
            "summary-model": {"provider": "gpt", "model": "summary", "api_key": "key"},
            "fallback-model": {"provider": "gpt", "model": "fallback", "api_key": "key"},
        },
    }


class _StubBambooConfig:
    def __init__(self, models_document: dict, *, agent_document: dict) -> None:
        self.models_document = models_document
        self.agent_document = agent_document

    def get(self, name: str, default: object = None) -> object:
        if name == "models":
            return self.models_document
        if name == "bamboo_main_agent":
            return self.agent_document
        return default


class _StaticLLMClient(LLMClient):
    def __init__(self, content: str) -> None:
        self.content = content
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content=self.content, model="test", provider="test")


class _FailingLLMClient(LLMClient):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        raise LLMRequestError("temporary", error_type="server_error", retryable=True)
