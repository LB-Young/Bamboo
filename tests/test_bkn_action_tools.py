"""Tests for BKN-private action tools."""

from __future__ import annotations

import json
from pathlib import Path

import anyio

from bamboo.bkn.action_runner import execute_action, prepare_action
from bamboo.bkn.graph import BknGraph
from bamboo.bkn.loader import load_bkn_definition
from bamboo.bkn.models import BknNode, BknNodeId, NodeKind
from bamboo.bkn.registry import BKNRegistry
from bamboo.bkn.store import BKNStore
from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.llms import LLMFactory
from bamboo.runtime.runtime_context import RuntimeContextBuilder
from bamboo.security.permission_policy import PermissionPolicy, PermissionRequest
from bamboo.tools.buildin.bkn_action_execute import BKNActionExecuteTool
from bamboo.tools.buildin.bkn_action_prepare import BKNActionPrepareTool
from bamboo.tools.buildin.bkn_list_actions import BKNListActionsTool


def test_bkn_action_prepare_restricts_to_platform_dir(tmp_path: Path) -> None:
    root = _platform_with_action(tmp_path, entrypoint="../escape.sh")
    definition = load_bkn_definition(root)

    try:
        prepare_action(definition, action_id="Sync")
    except Exception as exc:
        assert "escapes platform directory" in str(exc)
    else:
        raise AssertionError("expected prepare_action to reject escaped script")


def test_bkn_action_execute_runs_private_script(tmp_path: Path) -> None:
    root = _platform_with_action(tmp_path)
    definition = load_bkn_definition(root)

    async def run_test() -> None:
        result = await execute_action(definition, action_id="Sync", arguments={"content_id": "content:one"})
        assert result["exit_code"] == 0
        assert "content:one" in result["stdout"]

    anyio.run(run_test)


def test_bkn_action_tools_use_registry_and_execute_risk(tmp_path: Path) -> None:
    root = _platform_with_action(tmp_path)
    registry = BKNRegistry(bkn_dirs=[tmp_path], store=BKNStore(root=tmp_path / "storage" / "bkn"))
    task = _task(tmp_path)
    runtime_context = RuntimeContextBuilder(
        event_bus=_DummyEventBus(),
        llm_factory=LLMFactory.from_mapping(_model_document()),
        bkn_registry=registry,
    ).build(task)
    list_tool = BKNListActionsTool()
    prepare_tool = BKNActionPrepareTool()
    execute_tool = BKNActionExecuteTool()
    for tool in (list_tool, prepare_tool, execute_tool):
        tool.bind_runtime_context(runtime_context=runtime_context, task=task)

    async def run_test() -> None:
        listed = await list_tool.execute(platform_id="billing", entity_class="Content")
        assert "Sync" in listed.content
        prepared = await prepare_tool.execute(platform_id="billing", action_id="Sync", arguments={"content_id": "content:one"})
        assert prepared.metadata is not None
        assert prepared.metadata["script_path"].startswith(str(root))
        executed = await execute_tool.execute(platform_id="billing", action_id="Sync", arguments={"content_id": "content:one"})
        assert executed.success
        assert "content:one" in executed.content

    anyio.run(run_test)
    risk = PermissionPolicy().assess_risk(
        PermissionRequest(
            session_id="s",
            task_id="t",
            tool_call_id="c",
            tool_name="bkn_action_execute",
            arguments={},
            risk_level=execute_tool.risk_level,
        )
    )
    assert risk.risk_level == "execute"
    assert risk.requires_confirmation is True


def _platform_with_action(tmp_path: Path, *, entrypoint: str = "scripts/sync.sh") -> Path:
    root = tmp_path / "platforms" / "billing"
    (root / "actions").mkdir(parents=True)
    (root / "scripts").mkdir()
    root.joinpath("manifest.yaml").write_text(
        "\n".join(
            [
                "platform_id: billing",
                "name: Billing",
                "domain: billing",
                "owners:",
                '  - "@tester"',
                "status: active",
                "data_source_kind: static",
                "action_allowlist:",
                "  - Sync",
                "",
            ]
        ),
        encoding="utf-8",
    )
    root.joinpath("schema.json").write_text(
        json.dumps(
            {
                "platform_id": "billing",
                "version": 1,
                "classes": {"Content": {"actions": ["Sync"]}},
                "relations": {},
                "action_registry": {"Sync": {"description": "Sync content"}},
            }
        ),
        encoding="utf-8",
    )
    root.joinpath("actions", "sync.yaml").write_text(
        "\n".join(
            [
                "actions:",
                "  Sync:",
                "    description: Sync content privately",
                f"    entrypoint: {entrypoint}",
                "    risk_level: execute",
                "    arguments_schema:",
                "      required:",
                "        - content_id",
                "",
            ]
        ),
        encoding="utf-8",
    )
    root.joinpath("scripts", "sync.sh").write_text(
        "python - <<'PY'\nimport json, os\nprint(json.loads(os.environ['BKN_ACTION_ARGS'])['content_id'])\nPY\n",
        encoding="utf-8",
    )
    graph = BknGraph(root=root, platform_id="billing")
    graph.upsert_node(
        BknNode(
            id=BknNodeId("content:one"),
            platform_id="billing",
            kind=NodeKind.ENTITY,
            ontology_class="Content",
            name="Content One",
        )
    )
    return root


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


class _DummyEventBus:
    def subscribe(self, *args, **kwargs):
        return lambda: None
