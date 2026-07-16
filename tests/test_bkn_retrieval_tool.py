"""Tests for bkn_retrieval tool."""

from __future__ import annotations

import shutil
from pathlib import Path

import anyio
import pytest

from bamboo.bkn.registry import BKNRegistry
from bamboo.bkn.store import BKNStore
from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.tools.buildin.bkn_retrieval import BKNRetrievalTool

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bkn" / "personal-media"


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_bkn_retrieval_tool_returns_matches(tmp_path: Path) -> None:
    bkn_dir = tmp_path / "bkn"
    shutil.copytree(FIXTURE_ROOT, bkn_dir / "personal-media")
    registry = BKNRegistry(bkn_dirs=[bkn_dir], store=BKNStore(root=tmp_path / "storage" / "bkn"))
    tool = _bound_tool(registry=registry, task=_task(tmp_path))

    async def run_test() -> None:
        result = await tool.execute(query="Agent Memory", network="personal-media", max_hops=1)
        assert result.success
        assert "content:agent-memory-design" in result.content
        assert result.metadata is not None
        assert result.metadata["matches"][0]["entity_id"] == "content:agent-memory-design"

    anyio.run(run_test)


def test_bkn_retrieval_tool_returns_empty_results(tmp_path: Path) -> None:
    registry = BKNRegistry(bkn_dirs=[tmp_path / "missing"], store=BKNStore(root=tmp_path / "storage" / "bkn"))
    tool = _bound_tool(registry=registry, task=_task(tmp_path))

    async def run_test() -> None:
        result = await tool.execute(query="nothing")
        assert result.success
        assert result.content == '<bkn_results query="nothing" network="auto" count="0" />'
        assert result.metadata == {"query": "nothing", "network": "auto", "limit": 5, "max_hops": 2, "matches": []}

    anyio.run(run_test)


def _bound_tool(*, registry: BKNRegistry, task: Task) -> BKNRetrievalTool:
    runtime_context = RuntimeContextBuilder(
        event_bus=_DummyEventBus(),
        llm_factory=LLMFactory.from_mapping(_model_document()),
        bkn_registry=registry,
    ).build(task)
    tool = BKNRetrievalTool(bkn_registry=registry)
    tool.bind_runtime_context(runtime_context=runtime_context, task=task)
    return tool


def _task(project_root: Path) -> Task:
    project_root.mkdir(parents=True, exist_ok=True)
    run_params = RunParams(
        message="hello",
        model="test-model",
        project=str(project_root),
        session_mode=SessionMode.chat,
        task_id="task-bkn",
        session_id="session-bkn",
    )
    session = Session(
        session_id="session-bkn",
        model="test-model",
        provider="deepseek",
        context=Context(
            session_id="session-bkn",
            project_root=project_root,
            memory_dir=Path.cwd(),
            system_prompt="system",
            metadata={"prompt_mode": "chat"},
        ),
        current_task_id="task-bkn",
    )
    session.add_message("user", run_params.message)
    return Task(
        platform="cli",
        session_id="session-bkn",
        task_id="task-bkn",
        user_query=run_params.message,
        session=session,
        config={},
        run_params=run_params,
        memory_dir=Path.cwd(),
    )


def _model_document() -> dict:
    return {
        "default_model": "test-model",
        "models": {
            "test-model": {
                "provider": "deepseek",
                "model": "provider-model-id",
                "api_key": "test-api-key",
                "base_url": "https://llm.test/v1",
            }
        },
    }


class _DummyEventBus:
    def subscribe(self, *args, **kwargs):
        return lambda: None
