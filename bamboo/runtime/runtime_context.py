"""Agent 运行上下文构建器。

该模块集中创建一次 Task 执行所需的运行依赖，让 AgentRuntime 专注
执行 OTA 循环，而不是负责装配工具、prompt、模型客户端和压缩器。
"""

from __future__ import annotations

from dataclasses import dataclass

from bamboo.bkn import BKNRegistry, create_bkn_registry
from bamboo.factory.event_bus import EventBus
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import AuditEvent
from bamboo.llms import LLMClient, LLMFactory, LLMRoute, LLMRouter
from bamboo.llms.config import ModelConfig
from bamboo.memory.manager import MemoryManager
from bamboo.runtime.context_compactor import ContextBudgetPolicy, ContextCompactor, TokenCounter
from bamboo.runtime.prompt import AgentPromptBuilder
from bamboo.security import PermissionPolicy, PermissionResolver, ToolAuditLogger, create_permission_resolver
from bamboo.skills import SkillRegistry, create_skill_registry
from bamboo.subagents import SubagentRegistry, create_subagent_registry
from bamboo.tools import ToolRegistry, get_tool_registry
from bamboo.tools.mcp import MCPManager


@dataclass(slots=True)
class RuntimeContext:
    """保存 AgentRuntime 执行一个 Task 需要的稳定依赖。"""

    task: Task
    session: Session
    event_bus: EventBus
    llm_factory: LLMFactory
    llm_router: LLMRouter
    main_route: LLMRoute
    compaction_route: LLMRoute
    auxiliary_routes: dict[str, LLMRoute]
    model_name: str
    compaction_model_name: str
    model_config: ModelConfig
    llm_client: LLMClient
    compaction_llm_client: LLMClient
    tool_registry: ToolRegistry
    prompt_builder: AgentPromptBuilder
    context_compactor: ContextCompactor
    bkn_registry: BKNRegistry | None = None
    memory_manager: object | None = None
    skill_registry: SkillRegistry | None = None
    subagent_registry: SubagentRegistry | None = None
    mcp_manager: MCPManager | None = None
    permission_policy: PermissionPolicy | None = None
    permission_resolver: PermissionResolver | None = None
    audit_logger: ToolAuditLogger | None = None
    trace_recorder: object | None = None
    mcp_manager_owned: bool = False

    def route_for_role(self, role: str) -> LLMRoute:
        """Return an auxiliary model route by role, falling back to main-compatible routing."""
        normalized = role.strip().lower().replace("-", "_")
        route = self.auxiliary_routes.get(normalized)
        if route is not None:
            return route
        route = self.llm_router.route_for_role(normalized, default_model_name=self.model_name)
        self.auxiliary_routes[normalized] = route
        return route

    def client_for_role(self, role: str) -> LLMClient:
        """Return the active LLM client for an auxiliary role."""
        return self.llm_router.client_for(self.route_for_role(role))

    def config_for_role(self, role: str) -> ModelConfig:
        """Return the active model config for an auxiliary role."""
        return self.llm_router.config_for(self.route_for_role(role))

    def model_name_for_role(self, role: str) -> str:
        """Return the active model name for an auxiliary role."""
        return self.route_for_role(role).active_model_name

    async def close(self) -> None:
        """Release resources owned by this runtime context."""
        if self.mcp_manager is None or not self.mcp_manager_owned:
            return
        self.mcp_manager.stop_all()
        await self.event_bus.emit(
            AuditEvent(
                session_id=self.task.session_id,
                task_id=self.task.task_id,
                action="mcp_runtime_context_closed",
                result=_mcp_cleanup_result(self.mcp_manager),
                approved=not self.mcp_manager.stop_errors,
            )
        )


class RuntimeContextBuilder:
    """为 TaskRuntime 统一装配 Agent 执行依赖。"""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        llm_factory: LLMFactory,
        tool_registry: ToolRegistry | None = None,
        prompt_builder: AgentPromptBuilder | None = None,
        context_compactor: ContextCompactor | None = None,
        skill_registry: SkillRegistry | None = None,
        subagent_registry: SubagentRegistry | None = None,
        memory_manager: MemoryManager | None = None,
        bkn_registry: BKNRegistry | None = None,
        compaction_policy: ContextBudgetPolicy | None = None,
        token_counter: TokenCounter | None = None,
        model_name: str | None = None,
        compaction_model_name: str | None = None,
        permission_policy: PermissionPolicy | None = None,
        permission_resolver: PermissionResolver | None = None,
        audit_logger: ToolAuditLogger | None = None,
        mcp_enabled: bool = True,
    ) -> None:
        """初始化运行上下文构建所需的共享依赖。"""
        self.event_bus = event_bus
        self.llm_factory = llm_factory
        self.tool_registry = tool_registry or get_tool_registry()
        self.skill_registry = skill_registry or create_skill_registry()
        self.subagent_registry = subagent_registry
        self.memory_manager = memory_manager or MemoryManager()
        self.bkn_registry = bkn_registry or create_bkn_registry()
        self.prompt_builder = prompt_builder or AgentPromptBuilder(
            tool_registry=self.tool_registry,
            skill_registry=self.skill_registry,
            memory_manager=self.memory_manager,
        )
        if prompt_builder is not None and getattr(prompt_builder, "memory_manager", None) is None:
            prompt_builder.memory_manager = self.memory_manager
        self.context_compactor = context_compactor
        self.compaction_policy = compaction_policy
        self.token_counter = token_counter
        self.model_name = model_name
        self.compaction_model_name = compaction_model_name
        self.permission_policy = permission_policy or PermissionPolicy()
        self.permission_resolver = permission_resolver
        self.audit_logger = audit_logger or ToolAuditLogger()
        self.mcp_enabled = mcp_enabled
        self.mcp_manager: MCPManager | None = None
        self._owns_mcp_manager = False
        self._mcp_loaded = False

    def build(self, task: Task) -> RuntimeContext:
        """根据 Task 配置创建 AgentRuntime 可直接使用的上下文。"""
        self._ensure_mcp_tools(task)
        model_name = self.model_name or self._resolve_agent_model_name(task)
        llm_router = LLMRouter(self.llm_factory, config=task.config)
        main_route = llm_router.main_route(
            model_name,
            fallback_model_name=self._resolve_agent_fallback_model_name(task, model_name),
        )
        if self.compaction_model_name:
            compaction_route = llm_router.auxiliary_route("compaction", model_name=self.compaction_model_name)
        else:
            compaction_route = llm_router.route_for_role("compaction", default_model_name=model_name)
        auxiliary_routes = {"compaction": compaction_route}
        compaction_model_name = compaction_route.active_model_name
        model_config = llm_router.config_for(main_route)
        llm_client = llm_router.client_for(main_route)
        compaction_llm_client = llm_router.client_for(compaction_route)
        self.prompt_builder.set_model_config(model_config)
        context_compactor = self.context_compactor or ContextCompactor(
            llm_client=compaction_llm_client,
            model_config=model_config,
            llm_router=llm_router,
            route=compaction_route,
            token_counter=self.token_counter,
            policy=self.compaction_policy,
        )

        return RuntimeContext(
            task=task,
            session=task.session,
            event_bus=self.event_bus,
            llm_factory=self.llm_factory,
            llm_router=llm_router,
            main_route=main_route,
            compaction_route=compaction_route,
            auxiliary_routes=auxiliary_routes,
            model_name=model_name,
            compaction_model_name=compaction_model_name,
            model_config=model_config,
            llm_client=llm_client,
            compaction_llm_client=compaction_llm_client,
            tool_registry=self.tool_registry,
            prompt_builder=self.prompt_builder,
            context_compactor=context_compactor,
            bkn_registry=self.bkn_registry,
            memory_manager=self.memory_manager,
            skill_registry=self.skill_registry,
            subagent_registry=self.subagent_registry or create_subagent_registry(task.run_params.project),
            mcp_manager=self.mcp_manager,
            permission_policy=self.permission_policy,
            permission_resolver=self.permission_resolver or create_permission_resolver(task.run_params),
            audit_logger=self.audit_logger,
            mcp_manager_owned=self._owns_mcp_manager,
        )

    def _ensure_mcp_tools(self, task: Task) -> None:
        """按配置启动 MCP servers，并把工具注册进 ToolRegistry。"""
        if self._mcp_loaded:
            return
        if not self.mcp_enabled:
            self._mcp_loaded = True
            self.mcp_manager = MCPManager.from_config({})
            self._owns_mcp_manager = False
            return
        mcp_document = task.config.get("mcp", {})
        manager = MCPManager.from_config(mcp_document if isinstance(mcp_document, dict) else {})
        if not manager.configs:
            self._mcp_loaded = True
            self.mcp_manager = manager
            self._owns_mcp_manager = False
            return
        manager.start_all()
        manager.register_tools(self.tool_registry)
        self.mcp_manager = manager
        self._owns_mcp_manager = True
        self._mcp_loaded = True

    async def close(self, task: Task | None = None) -> None:
        """Close resources owned by this builder and reset lazy runtime state."""
        if self.mcp_manager is None or not self._owns_mcp_manager:
            self._mcp_loaded = False
            self.mcp_manager = None
            self._owns_mcp_manager = False
            return
        manager = self.mcp_manager
        manager.stop_all()
        if task is not None:
            await self.event_bus.emit(
                AuditEvent(
                    session_id=task.session_id,
                    task_id=task.task_id,
                    action="mcp_runtime_builder_closed",
                    result=_mcp_cleanup_result(manager),
                    approved=not manager.stop_errors,
                )
            )
        self._mcp_loaded = False
        self.mcp_manager = None
        self._owns_mcp_manager = False

    def _resolve_agent_model_name(self, task: Task) -> str:
        """根据任务覆盖、主 Agent 配置和默认模型确定执行模型名。"""
        if task.session.model:
            return task.session.model
        main_agent_config = task.config.get("bamboo_main_agent", {})
        configured_name = main_agent_config.get("model") if isinstance(main_agent_config, dict) else None
        if isinstance(configured_name, str) and configured_name and self.llm_factory.has_model(configured_name):
            return configured_name
        return self.llm_factory.default_model_name

    def _resolve_agent_fallback_model_name(self, task: Task, agent_model_name: str) -> str:
        """读取主模型 fallback；无效或等于主模型时视为未配置。"""
        main_agent_config = task.config.get("bamboo_main_agent", {})
        configured_name = main_agent_config.get("fallback_model") if isinstance(main_agent_config, dict) else None
        if (
            isinstance(configured_name, str)
            and configured_name
            and configured_name != agent_model_name
            and self.llm_factory.has_model(configured_name)
        ):
            return configured_name
        return ""

def _mcp_cleanup_result(manager: MCPManager) -> str:
    """Render a concise cleanup summary for audit events."""
    parts = [f"stopped={manager.stopped}", f"start_errors={len(manager.errors)}", f"stop_errors={len(manager.stop_errors)}"]
    if manager.errors:
        parts.append(f"start_error_servers={','.join(sorted(manager.errors))}")
    if manager.stop_errors:
        parts.append(f"stop_error_servers={','.join(sorted(manager.stop_errors))}")
    return " ".join(parts)
