"""Runtime for same-process restricted subagents."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import uuid4

from bamboo.factory.session import SessionFactory
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SubagentFinishEvent, SubagentStartEvent
from bamboo.helpers.requests_params import RunParams
from bamboo.runtime.runtime_context import RuntimeContext, RuntimeContextBuilder
from bamboo.runtime.subagent_workspace import SubagentWorkspaceManager
from bamboo.subagents.models import SubagentDefinition, SubagentRunResult
from bamboo.subagents.registry import SubagentRegistry
from bamboo.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from bamboo.runtime.agent_runtime import AgentRecoveryPolicy


class SubagentRuntime:
    """Creates a child task with a narrowed tool registry and runs AgentRuntime."""

    def __init__(
        self,
        *,
        parent_context: RuntimeContext,
        parent_task: Task,
        registry: SubagentRegistry,
        session_factory: SessionFactory | None = None,
        workspace_manager: SubagentWorkspaceManager | None = None,
        recovery_policy: "AgentRecoveryPolicy | None" = None,
    ) -> None:
        self.parent_context = parent_context
        self.parent_task = parent_task
        self.registry = registry
        self.session_factory = session_factory or SessionFactory()
        self.workspace_manager = workspace_manager or SubagentWorkspaceManager()
        self.recovery_policy = recovery_policy or self._default_recovery_policy()

    async def run(
        self,
        *,
        subagent_type: str,
        description: str,
        prompt: str,
        task_id: str | None = None,
    ) -> SubagentRunResult:
        """Run a restricted child agent and return its final output."""
        definition = self.registry.get(subagent_type)
        if definition is None:
            available = ", ".join(self.registry.available_names()) or "none"
            raise KeyError(f"Subagent not found: {subagent_type}. Available subagents: {available}")

        workspace = self.workspace_manager.prepare(
            definition=definition,
            project_root=self.parent_task.session.context.project_root,
            tool_registry=self.parent_context.tool_registry,
        )
        child_task = self._create_child_task(
            definition,
            description=description,
            prompt=prompt,
            task_id=task_id,
            project_path=workspace.path,
        )
        await self.parent_context.event_bus.emit(
            SubagentStartEvent(
                session_id=self.parent_task.session_id,
                task_id=self.parent_task.task_id,
                subagent_name=definition.name,
                child_task_id=child_task.task_id,
                parent_session_id=self.parent_task.session_id,
                parent_task_id=self.parent_task.task_id,
                description=description,
            )
        )
        child_tool_registry = self._restricted_tool_registry(definition)
        child_builder = RuntimeContextBuilder(
            event_bus=self.parent_context.event_bus,
            llm_factory=self.parent_context.llm_factory,
            tool_registry=child_tool_registry,
            skill_registry=self.parent_context.skill_registry,
            compaction_policy=self.parent_context.context_compactor.policy,
            token_counter=self.parent_context.context_compactor.token_counter,
            model_name=definition.model or self.parent_context.model_name,
            compaction_model_name=self.parent_context.compaction_model_name,
            permission_policy=self.parent_context.permission_policy,
            permission_resolver=self.parent_context.permission_resolver,
            audit_logger=self.parent_context.audit_logger,
            mcp_enabled=False,
        )
        from bamboo.runtime.agent_runtime import AgentRuntime

        runtime = AgentRuntime(
            runtime_context=child_builder.build(child_task),
            recovery_policy=self.recovery_policy,
        )
        completed = child_task
        error = ""
        try:
            completed = await runtime.run(child_task)
        except Exception as exc:
            completed.status = "failed"
            completed.error = str(exc)
            error = str(exc)
        diff = self.workspace_manager.collect_diff(workspace)
        self.workspace_manager.finalize(
            workspace,
            diff,
            success=completed.status == "completed" and not error,
            keep_on_success=definition.keep_workspace_on_success,
        )
        await self.parent_context.event_bus.emit(
            SubagentFinishEvent(
                session_id=self.parent_task.session_id,
                task_id=self.parent_task.task_id,
                subagent_name=definition.name,
                child_task_id=completed.task_id,
                child_session_id=completed.session_id,
                parent_session_id=self.parent_task.session_id,
                parent_task_id=self.parent_task.task_id,
                status=completed.status,
            )
        )
        return SubagentRunResult(
            subagent_name=definition.name,
            task_id=completed.task_id,
            session_id=completed.session_id,
            output=completed.output or error,
            status=completed.status,
            workspace_mode=workspace.mode,
            workspace_path=str(workspace.path) if workspace.isolated else "",
            changed_files=diff.changed_files,
            diff_stat=diff.diff_stat,
            diff_patch_path=diff.diff_patch_path,
            merge_required=diff.has_changes,
            workspace_retained=workspace.retained,
            workspace_note=workspace.note,
        )

    def _create_child_task(
        self,
        definition: SubagentDefinition,
        *,
        description: str,
        prompt: str,
        task_id: str | None,
        project_path,
    ) -> Task:
        child_task_id = task_id or str(uuid4())
        child_session_id = str(uuid4())
        child_prompt = self._build_child_prompt(definition, description=description, prompt=prompt)
        child_params = replace(
            self.parent_task.run_params,
            message=child_prompt,
            project=str(project_path),
            task_id=child_task_id,
            session_id=child_session_id,
        )
        session = self.session_factory.create(memory_dir_path=self.parent_task.memory_dir, run_params=child_params)
        session.context.metadata["parent_session_id"] = self.parent_task.session_id
        session.context.metadata["parent_task_id"] = self.parent_task.task_id
        session.context.metadata["subagent_name"] = definition.name
        if session.memory_store is not None:
            session.memory_store.save_session(
                mode=str(session.context.metadata.get("prompt_mode") or self.parent_task.run_params.session_mode),
                project_root=session.context.project_root,
                model=session.model,
                provider=session.provider,
                system_prompt=session.context.system_prompt,
                metadata=session.context.metadata,
            )
        task = Task(
            platform=self.parent_task.platform,
            session_id=child_session_id,
            task_id=child_task_id,
            user_query=child_prompt,
            session=session,
            config=self.parent_task.config,
            run_params=child_params,
            memory_dir=self.parent_task.memory_dir,
            metadata={
                "parent_session_id": self.parent_task.session_id,
                "parent_task_id": self.parent_task.task_id,
                "subagent_name": definition.name,
            },
        )
        return task

    def _build_child_prompt(self, definition: SubagentDefinition, *, description: str, prompt: str) -> str:
        allowed_tools = ", ".join(sorted(name for name, mode in definition.tools.items() if mode))
        return (
            f"You are Bamboo subagent `{definition.name}`.\n"
            f"Subagent description: {definition.description}\n"
            f"Delegated task: {description}\n\n"
            f"Permission boundary: {definition.permission}. "
            f"You may only use these tools if available: {allowed_tools or 'none'}.\n"
            "Do not modify files unless this subagent profile explicitly allows write tools.\n"
            "Return a concise result for the parent agent.\n\n"
            f"Task prompt:\n{prompt}"
        )

    def _restricted_tool_registry(self, definition: SubagentDefinition) -> ToolRegistry:
        registry = ToolRegistry()
        for name, mode in definition.tools.items():
            if not mode:
                continue
            tool = self.parent_context.tool_registry.get(name)
            if tool is not None:
                registry.register(tool, source=f"subagent:{definition.name}")
        return registry

    @staticmethod
    def _default_recovery_policy() -> "AgentRecoveryPolicy":
        from bamboo.runtime.agent_runtime import AgentRecoveryPolicy

        return AgentRecoveryPolicy(max_iterations=8)
