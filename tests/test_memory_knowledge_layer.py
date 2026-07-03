"""Tests for editable memory knowledge prompt context."""

from __future__ import annotations

from pathlib import Path

import pytest

from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.memory.get_memory_path import get_memory_dir_name
from bamboo.memory.manager import MemoryManager
from bamboo.runtime.runtime_context import RuntimeContextBuilder


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_memory_manager_creates_chat_templates_without_injecting_empty_templates(tmp_path: Path) -> None:
    manager = MemoryManager()
    session = _session(mode="chat", project_root=tmp_path)

    context = manager.load_prompt_context(session)

    assert context.scope.kind == "chat"
    assert context.knowledge_dir.parts[-3:] == ("dates", "chat", "knowledge")
    assert (context.knowledge_dir / "global.md").is_file()
    assert (context.knowledge_dir / "profile.md").is_file()
    assert (context.knowledge_dir / "preferences.md").is_file()
    assert "# Profile" in (context.knowledge_dir / "profile.md").read_text(encoding="utf-8")
    assert context.content == ""


def test_memory_manager_loads_chat_global_knowledge_next_prompt(tmp_path: Path) -> None:
    manager = MemoryManager()
    session = _session(mode="chat", project_root=tmp_path)
    first_context = manager.load_prompt_context(session)
    (first_context.knowledge_dir / "global.md").write_text(
        "- Prefer concise Chinese answers. source: session-a/task-a\n",
        encoding="utf-8",
    )

    second_context = manager.load_prompt_context(session)

    assert "global.md" in second_context.content
    assert "Prefer concise Chinese answers" in second_context.content


def test_memory_manager_keeps_project_knowledge_isolated(tmp_path: Path) -> None:
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    manager = MemoryManager()

    session_a = _session(mode="project", project_root=project_a)
    context_a = manager.load_prompt_context(session_a)
    (context_a.knowledge_dir / "global.md").write_text(
        "- Project A uses Redis. source: session-a/task-a\n",
        encoding="utf-8",
    )
    project_global_dir = context_a.knowledge_dirs[0]
    assert project_global_dir.parts[-3:] == ("memory", "projects", "knowledge")
    (project_global_dir / "global.md").write_text(
        "- All projects use pytest before final answers. source: session-global/task-global\n",
        encoding="utf-8",
    )

    session_b = _session(mode="project", project_root=project_b)
    context_b = manager.load_prompt_context(session_b)

    assert get_memory_dir_name(project_a) in str(context_a.knowledge_dir)
    assert get_memory_dir_name(project_b) in str(context_b.knowledge_dir)
    content_a = manager.load_prompt_context(session_a).content
    content_b = manager.load_prompt_context(session_b).content
    assert "Project A uses Redis" in content_a
    assert "All projects use pytest" in content_a
    assert "All projects use pytest" in content_b
    assert "Project A uses Redis" not in context_b.content


def test_runtime_prompt_builder_injects_memory_knowledge(tmp_path: Path) -> None:
    manager = MemoryManager()
    project_root = tmp_path / "demo-project"
    project_root.mkdir()
    session = _session(mode="project", project_root=project_root)
    context = manager.load_prompt_context(session)
    (context.knowledge_dir / "global.md").write_text(
        "- Use pytest for verification. source: session-a/task-a\n",
        encoding="utf-8",
    )
    task = _task(session=session, project_root=project_root)

    runtime_context = RuntimeContextBuilder(
        event_bus=_DummyEventBus(),
        llm_factory=LLMFactory.from_mapping(_model_document()),
        memory_manager=manager,
    ).build(task)
    prompt = runtime_context.prompt_builder.build(session)

    assert "# Global Memory" in prompt.to_llm_request().system_prompt
    assert "Use pytest for verification" in prompt.to_llm_request().system_prompt


def _session(*, mode: str, project_root: Path) -> Session:
    return Session(
        session_id="session-a",
        model="test-model",
        provider="deepseek",
        context=Context(
            session_id="session-a",
            project_root=project_root,
            memory_dir=Path.cwd(),
            system_prompt="system",
            metadata={"prompt_mode": mode},
        ),
    )


def _task(*, session: Session, project_root: Path):
    from bamboo.factory.task_factory import Task

    run_params = RunParams(
        message="hello",
        model="test-model",
        project=str(project_root),
        session_mode=SessionMode.project,
        task_id="task-a",
        session_id=session.session_id,
    )
    return Task(
        platform="cli",
        session_id=session.session_id,
        task_id="task-a",
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


class _DummyEventBus:
    def subscribe(self, *args, **kwargs):
        return lambda: None
