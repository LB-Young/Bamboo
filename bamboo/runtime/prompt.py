"""Agent prompt 和上下文组织器。

该模块把 system prompt、消息历史、可用工具和恢复错误整理成稳定结构。
AgentRuntime 可以把这里的结果直接转换为统一 LLMRequest。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bamboo.factory.session import Session
from bamboo.llms import LLMMessage, LLMRequest
from bamboo.memory.manager import MemoryManager
from bamboo.skills import SkillRegistry
from bamboo.tools import ToolRegistry, get_tool_registry


@dataclass(slots=True)
class AgentPrompt:
    """保存一轮 Agent 循环所需的 prompt 材料。"""

    system_prompt: str
    messages: list[LLMMessage]
    tool_catalog: str
    skill_catalog: str
    tools: list[dict]
    memory_context: str = ""
    error_history: list[str] = field(default_factory=list)

    def render(self) -> str:
        """渲染为便于日志和调试查看的确定性文本块。"""
        sections = [
            "# System Prompt",
            self.system_prompt,
            "# Messages",
            "\n".join(f"[{message.role}] {message.content}" for message in self.messages) or "(none)",
            "# Available Tools",
            self.tool_catalog or "(none)",
            "# Available Skills",
            self.skill_catalog or "(none)",
        ]
        if self.memory_context:
            sections.extend(["# Memory Knowledge", self.memory_context])
        if self.error_history:
            sections.extend(["# Recoverable Errors", "\n".join(self.error_history)])
        return "\n\n".join(sections)

    def to_llm_request(self) -> LLMRequest:
        """把 Agent prompt 转换为与 Provider 无关的模型请求。"""
        system_sections = [self.system_prompt]
        if self.memory_context:
            system_sections.extend(["# Memory Knowledge", self.memory_context])
        if self.tool_catalog:
            system_sections.extend(["# Available Tools", self.tool_catalog])
        if self.skill_catalog:
            system_sections.extend(["# Available Skills", self.skill_catalog])
        if self.error_history:
            system_sections.extend(["# Recoverable Errors", "\n".join(self.error_history)])
        return LLMRequest(
            system_prompt="\n\n".join(section for section in system_sections if section),
            messages=list(self.messages),
            tools=list(self.tools),
        )


class AgentPromptBuilder:
    """从 Session、工具注册表和错误历史构建 prompt。"""

    def __init__(
        self,
        *,
        tool_registry: ToolRegistry | None = None,
        skill_registry: SkillRegistry | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        """初始化 Prompt Builder，并固定当前 Agent 可见的工具注册表。"""
        self.tool_registry = tool_registry or get_tool_registry()
        self.skill_registry = skill_registry
        self.memory_manager = memory_manager

    def build(self, session: Session, *, error_history: list[str] | None = None) -> AgentPrompt:
        """构建一轮 Agent 循环的 prompt 快照。"""
        messages = [
            LLMMessage(
                role=message.role,
                content=message.content,
                tool_calls=list(message.tool_calls),
                tool_call_id=message.tool_call_id,
                tool_name=message.tool_name,
            )
            for message in session.active_messages()
        ]
        tools = self._get_tool_schemas()
        return AgentPrompt(
            system_prompt=session.context.system_prompt,
            messages=messages,
            tool_catalog=self._build_tool_catalog(),
            skill_catalog=self._build_skill_catalog(),
            memory_context=self._build_memory_context(session),
            tools=tools,
            error_history=error_history or [],
        )

    def _build_tool_catalog(self) -> str:
        """渲染简洁的内置工具目录。"""
        rows = []
        for tool in self.tool_registry.get_tools():
            rows.append(f"- `{tool.name}`: {tool.description}")
        return "\n".join(rows)

    def _get_tool_schemas(self) -> list[dict]:
        """返回当前所有已启用工具的结构化调用 Schema。"""
        return self.tool_registry.schemas()

    def _build_skill_catalog(self) -> str:
        """渲染可用 Skill 摘要。"""
        if self.skill_registry is None:
            return ""
        return self.skill_registry.render_catalog()

    def _build_memory_context(self, session: Session) -> str:
        """Render editable memory knowledge for the active session."""
        if self.memory_manager is None:
            return ""
        return self.memory_manager.load_prompt_context(session).content
