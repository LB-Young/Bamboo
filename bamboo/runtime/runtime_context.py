"""Agent 运行上下文构建器。

该模块集中创建一次 Task 执行所需的运行依赖，让 AgentRuntime 专注
执行 OTA 循环，而不是负责装配工具、prompt、模型客户端和压缩器。
"""

from __future__ import annotations

from dataclasses import dataclass

from bamboo.factory.event_bus import EventBus
from bamboo.factory.session import Session
from bamboo.factory.task_factory import Task
from bamboo.llms import LLMClient, LLMFactory
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
    model_name: str
    compaction_model_name: str
    model_config: ModelConfig
    llm_client: LLMClient
    compaction_llm_client: LLMClient
    tool_registry: ToolRegistry
    prompt_builder: AgentPromptBuilder
    context_compactor: ContextCompactor
    memory_manager: object | None = None
    skill_registry: SkillRegistry | None = None
    subagent_registry: SubagentRegistry | None = None
    mcp_manager: MCPManager | None = None
    permission_policy: PermissionPolicy | None = None
    permission_resolver: PermissionResolver | None = None
    audit_logger: ToolAuditLogger | None = None
    trace_recorder: object | None = None


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
        self._mcp_loaded = False

    def build(self, task: Task) -> RuntimeContext:
        """根据 Task 配置创建 AgentRuntime 可直接使用的上下文。"""
        self._ensure_mcp_tools(task)
        model_name = self.model_name or self._resolve_agent_model_name(task)
        compaction_model_name = self.compaction_model_name or self._resolve_compaction_model_name(task, model_name)
        model_config = self.llm_factory.get_model_config(model_name)
        llm_client = self.llm_factory.get_client(model_name)
        compaction_llm_client = self.llm_factory.get_client(compaction_model_name)
        context_compactor = self.context_compactor or ContextCompactor(
            llm_client=compaction_llm_client,
            model_config=model_config,
            token_counter=self.token_counter,
            policy=self.compaction_policy,
        )

        return RuntimeContext(
            task=task,
            session=task.session,
            event_bus=self.event_bus,
            llm_factory=self.llm_factory,
            model_name=model_name,
            compaction_model_name=compaction_model_name,
            model_config=model_config,
            llm_client=llm_client,
            compaction_llm_client=compaction_llm_client,
            tool_registry=self.tool_registry,
            prompt_builder=self.prompt_builder,
            context_compactor=context_compactor,
            memory_manager=self.memory_manager,
            skill_registry=self.skill_registry,
            subagent_registry=self.subagent_registry or create_subagent_registry(task.run_params.project),
            mcp_manager=self.mcp_manager,
            permission_policy=self.permission_policy,
            permission_resolver=self.permission_resolver or create_permission_resolver(task.run_params),
            audit_logger=self.audit_logger,
        )

    def _ensure_mcp_tools(self, task: Task) -> None:
        """按配置启动 MCP servers，并把工具注册进 ToolRegistry。"""
        if self._mcp_loaded:
            return
        if not self.mcp_enabled:
            self._mcp_loaded = True
            self.mcp_manager = MCPManager.from_config({})
            return
        mcp_document = task.config.get("mcp", {})
        manager = MCPManager.from_config(mcp_document if isinstance(mcp_document, dict) else {})
        if not manager.configs:
            self._mcp_loaded = True
            self.mcp_manager = manager
            return
        manager.start_all()
        manager.register_tools(self.tool_registry)
        self.mcp_manager = manager
        self._mcp_loaded = True

    def _resolve_agent_model_name(self, task: Task) -> str:
        """根据任务覆盖、主 Agent 配置和默认模型确定执行模型名。"""
        if task.session.model:
            return task.session.model
        main_agent_config = task.config.get("bamboo_main_agent", {})
        configured_name = main_agent_config.get("model") if isinstance(main_agent_config, dict) else None
        if isinstance(configured_name, str) and configured_name and self.llm_factory.has_model(configured_name):
            return configured_name
        return self.llm_factory.default_model_name

    def _resolve_compaction_model_name(self, task: Task, agent_model_name: str) -> str:
        """读取可选压缩模型名；缺失时复用执行模型。"""
        main_agent_config = task.config.get("bamboo_main_agent", {})
        configured_name = (
            main_agent_config.get("compaction_model") if isinstance(main_agent_config, dict) else None
        )
        if isinstance(configured_name, str) and configured_name and self.llm_factory.has_model(configured_name):
            return configured_name
        return agent_model_name
