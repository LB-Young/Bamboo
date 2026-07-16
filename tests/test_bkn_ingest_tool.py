"""Tests for BKN ingest tools."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.tools.buildin.bkn_ingest import BKNIngestTool
from bamboo.tools.buildin.bkn_ingest_submit import BKNIngestSubmitTool


@pytest.fixture(autouse=True)
def isolated_bkn_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("bamboo.bkn.ingest.get_user_bkn_dir", lambda: tmp_path / "bkn")


def test_bkn_ingest_tool_creates_draft() -> None:
    tool = BKNIngestTool()

    async def run_test() -> None:
        result = await tool.execute(
            platform_id="billing",
            manifest_draft={"name": "Billing", "domain": "billing", "owners": ["@tester"]},
            schema={"classes": {"Customer": {"actions": []}}},
            nodes=[{"id": "customer:c001", "ontology_class": "Customer", "name": "Customer C001"}],
        )
        assert result.success
        assert result.metadata is not None
        assert Path(result.metadata["preview_path"]).is_file()

    anyio.run(run_test)


def test_bkn_ingest_submit_tool_emits_activation_event(tmp_path: Path) -> None:
    event_bus = _CapturingEventBus()
    task = _task(tmp_path)
    runtime_context = RuntimeContextBuilder(event_bus=event_bus, llm_factory=LLMFactory.from_mapping(_model_document())).build(task)
    ingest = BKNIngestTool()
    submit = BKNIngestSubmitTool()
    submit.bind_runtime_context(runtime_context=runtime_context, task=task)

    async def run_test() -> None:
        await ingest.execute(
            platform_id="billing",
            manifest_draft={"name": "Billing", "domain": "billing", "owners": ["@tester"], "status": "active"},
            schema={"classes": {"Customer": {"actions": []}}},
        )
        result = await submit.execute(platform_id="billing", approve=True)
        assert result.success
        assert any(event.action == "bkn.platform.activated" for event in event_bus.events)

    anyio.run(run_test)


def _task(project_root: Path) -> Task:
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
    return Task(
        platform="cli",
        session_id="session-bkn",
        task_id="task-bkn",
        user_query="hello",
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


class _CapturingEventBus:
    def __init__(self) -> None:
        self.events = []

    def subscribe(self, *args, **kwargs):
        return lambda: None

    async def emit(self, event):
        self.events.append(event)
