"""Task cancellation tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient

from bamboo.adapters.web.app import create_app
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.runtime.store import get_task_store, reset_task_store
from bamboo.runtime.task_runtime import TaskRuntime


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    reset_task_store()


def test_task_runtime_marks_cancelled_when_worker_is_cancelled(tmp_path: Path) -> None:
    async def run_test() -> None:
        runtime = TaskRuntime(
            llm_factory=LLMFactory.from_mapping(_model_document()),
            agent_factory=lambda event_bus: _SleepingAgent(),
        )
        task = runtime.create_task(RunParams(message="long task", project=str(tmp_path), model="test-model"))
        worker = asyncio.create_task(runtime.run_existing_task(task))
        await asyncio.sleep(0)
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

        snapshot = get_task_store().get(task.task_id)
        assert snapshot is not None
        assert snapshot.status == "cancelled"
        assert snapshot.metadata["stop_reason"] == "cancelled by user"

    anyio.run(run_test)


def test_web_stop_endpoint_marks_known_task_cancelled() -> None:
    app = create_app()
    snapshot = get_task_store().create_task(task_id="task-stop", session_id="session-stop", title="Stop me")
    assert snapshot.status == "created"

    response = TestClient(app).post("/api/tasks/task-stop/stop")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert get_task_store().get("task-stop").status == "cancelled"  # type: ignore[union-attr]


class _SleepingAgent:
    async def run(self, task):
        await asyncio.sleep(60)
        return task


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
