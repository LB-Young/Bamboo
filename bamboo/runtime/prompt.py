"""Agent prompt 和上下文组织器。

该模块把 system prompt、消息历史、可用工具和恢复错误整理成稳定结构。
AgentRuntime 可以把这里的结果直接转换为统一 LLMRequest。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bamboo.bkn import BKNRegistry
from bamboo.factory.session import Session
from bamboo.llms import LLMMessage, LLMRequest
from bamboo.llms.config import ModelCapabilities, ModelConfig
from bamboo.llms.media import image_summary
from bamboo.memory.manager import MemoryManager
from bamboo.prompts import PromptSection, read_provider_prompt_section_objects, render_prompt_sections
from bamboo.skills import SkillRegistry
from bamboo.tools import ToolRegistry, get_tool_registry

MAX_BKN_DOC_CHARS = 1600


@dataclass(slots=True)
class AgentPrompt:
    """保存一轮 Agent 循环所需的 prompt 材料。"""

    system_prompt: str
    messages: list[LLMMessage]
    tool_catalog: str
    skill_catalog: str
    tools: list[dict]
    memory_context: str = ""
    provider_context: str = ""
    prompt_sections: list[PromptSection] = field(default_factory=list)
    model_capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    error_history: list[str] = field(default_factory=list)

    def render(self) -> str:
        """渲染为便于日志和调试查看的确定性文本块。"""
        sections = [
            "# System Prompt",
            self.system_prompt,
            "# Prompt Sections",
            self._render_section_metadata(),
            "# Messages",
            "\n".join(
                f"[{message.role}] {message.content}"
                + (f"\n{image_summary(message.images)}" if message.images else "")
                for message in self.messages
            )
            or "(none)",
            "# Available Tools",
            self.tool_catalog or "(none)",
            "# Available Skills",
            self.skill_catalog or "(none)",
        ]
        if self.provider_context:
            sections.extend(["# Provider Prompt", self.provider_context])
        if self.memory_context:
            sections.extend(["# Global Memory", self.memory_context])
        if self.error_history:
            sections.extend(["# Recoverable Errors", "\n".join(self.error_history)])
        return "\n\n".join(sections)

    def to_llm_request(self) -> LLMRequest:
        """把 Agent prompt 转换为与 Provider 无关的模型请求。"""
        if self.prompt_sections:
            system_prompt = render_prompt_sections(self.prompt_sections)
            return LLMRequest(
                system_prompt=system_prompt,
                messages=list(self.messages),
                tools=list(self.tools),
            )
        system_sections = [self.system_prompt]
        if self.memory_context:
            system_sections.extend(["# Global Memory", self.memory_context])
        if self.provider_context:
            system_sections.extend(["# Provider Prompt", self.provider_context])
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

    def _render_section_metadata(self) -> str:
        """Render prompt section metadata for debug output."""
        if not self.prompt_sections:
            return "(none)"
        rows = []
        for section in sorted(self.prompt_sections, key=lambda item: (item.priority, item.name, item.source)):
            metadata = section.to_metadata()
            rows.append(
                f"- {metadata['priority']} `{metadata['name']}` "
                f"source=`{metadata['source']}` cacheable={metadata['cacheable']} "
                f"hash={metadata['content_hash'][:12]} chars={metadata['content_chars']}"
            )
        return "\n".join(rows)


class AgentPromptBuilder:
    """从 Session、工具注册表和错误历史构建 prompt。"""

    def __init__(
        self,
        *,
        tool_registry: ToolRegistry | None = None,
        skill_registry: SkillRegistry | None = None,
        memory_manager: MemoryManager | None = None,
        bkn_registry: BKNRegistry | None = None,
        model_config: ModelConfig | None = None,
    ) -> None:
        """初始化 Prompt Builder，并固定当前 Agent 可见的工具注册表。"""
        self.tool_registry = tool_registry or get_tool_registry()
        self.skill_registry = skill_registry
        self.memory_manager = memory_manager
        self.bkn_registry = bkn_registry
        self.model_config = model_config

    def set_model_config(self, model_config: ModelConfig) -> None:
        """更新当前 prompt builder 使用的模型配置。"""
        self.model_config = model_config

    def build(self, session: Session, *, error_history: list[str] | None = None) -> AgentPrompt:
        """构建一轮 Agent 循环的 prompt 快照。"""
        messages = [
            LLMMessage(
                role=message.role,
                content=message.content,
                images=list(message.images),
                tool_calls=list(message.tool_calls),
                tool_call_id=message.tool_call_id,
                tool_name=message.tool_name,
            )
            for message in session.active_messages()
        ]
        tools = self._get_tool_schemas()
        tool_catalog = self._build_tool_catalog()
        skill_catalog = self._build_skill_catalog()
        bkn_catalog = self._build_bkn_catalog()
        memory_context = self._build_memory_context(session)
        provider_context = self._build_provider_context()
        error_history = error_history or []
        return AgentPrompt(
            system_prompt=session.context.system_prompt,
            messages=messages,
            tool_catalog=tool_catalog,
            skill_catalog=skill_catalog,
            memory_context=memory_context,
            provider_context=provider_context,
            prompt_sections=self._build_prompt_sections(
                session=session,
                tool_catalog=tool_catalog,
                skill_catalog=skill_catalog,
                bkn_catalog=bkn_catalog,
                memory_context=memory_context,
                provider_context=provider_context,
                error_history=error_history,
            ),
            model_capabilities=self._model_capabilities(),
            tools=tools,
            error_history=error_history,
        )

    def _build_tool_catalog(self) -> str:
        """渲染简洁的内置工具目录。"""
        if not self._model_capabilities().tool_calling:
            return ""
        rows = []
        for tool in self.tool_registry.get_tools():
            rows.append(f"- `{tool.name}`: {tool.description}")
        return "\n".join(rows)

    def _get_tool_schemas(self) -> list[dict]:
        """返回当前所有已启用工具的结构化调用 Schema。"""
        if not self._model_capabilities().tool_calling:
            return []
        return self.tool_registry.schemas()

    def _build_skill_catalog(self) -> str:
        """渲染可用 Skill 摘要。"""
        if self.skill_registry is None:
            return ""
        return self.skill_registry.render_catalog()

    def _build_bkn_catalog(self) -> str:
        """Render committed BKN.md files as a compact BKN directory."""
        if self.bkn_registry is None:
            return ""
        try:
            definitions = self.bkn_registry.list()
        except OSError:
            return ""
        chunks = [
            "# Available BKNs",
            "",
            "Bamboo Knowledge Networks provide business objects, relationships, data sources, operators, and action metadata.",
            "Use the summaries below to decide whether a user request needs a BKN. When one is relevant, load that BKN's `preview.md` before detailed reasoning, then use BKN tools for concrete entities and relationships.",
        ]
        found = False
        for definition in definitions:
            bkn_doc_path = definition.root / "BKN.md"
            if not bkn_doc_path.is_file():
                continue
            content = bkn_doc_path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            preview_path = definition.root / "preview.md"
            if len(content) > MAX_BKN_DOC_CHARS:
                content = content[: MAX_BKN_DOC_CHARS - 3].rstrip() + "..."
            chunks.extend(
                [
                    "",
                    f"## {definition.name}",
                    "",
                    content,
                    "",
                    f"- Full BKN context: `{preview_path}`",
                ]
            )
            found = True
        return "\n".join(chunks) if found else ""

    def _build_memory_context(self, session: Session) -> str:
        """Render editable memory knowledge for the active session."""
        if self.memory_manager is None:
            return ""
        return self.memory_manager.load_prompt_context(session).content

    def _build_provider_context(self) -> str:
        """Render provider-specific prompt sections for the active model."""
        if self.model_config is None:
            return ""
        sections = [section.content for section in read_provider_prompt_section_objects(self.model_config.prompt_profile)]
        capability_section = self._build_capabilities_section(self.model_config)
        if capability_section:
            sections.append(capability_section)
        return "\n\n".join(section for section in sections if section)

    def _build_prompt_sections(
        self,
        *,
        session: Session,
        tool_catalog: str,
        skill_catalog: str,
        bkn_catalog: str,
        memory_context: str,
        provider_context: str,
        error_history: list[str],
    ) -> list[PromptSection]:
        """Build runtime prompt sections with debuggable metadata."""
        sections = [
            PromptSection(
                name="system-prompt",
                source="session.context.system_prompt",
                priority=100,
                cacheable=True,
                content=session.context.system_prompt,
            )
        ]
        if memory_context:
            sections.append(
                PromptSection(
                    name="global-memory",
                    source="memory-manager",
                    priority=300,
                    cacheable=False,
                    content=f"# Global Memory\n\n{memory_context}",
                )
            )
        if provider_context:
            sections.append(
                PromptSection(
                    name="provider-prompt",
                    source=f"provider:{self.model_config.prompt_profile if self.model_config else ''}",
                    priority=400,
                    cacheable=True,
                    content=f"# Provider Prompt\n\n{provider_context}",
                )
            )
        if tool_catalog:
            sections.append(
                PromptSection(
                    name="available-tools",
                    source="tool-registry",
                    priority=500,
                    cacheable=False,
                    content=f"# Available Tools\n\n{tool_catalog}",
                )
            )
        if skill_catalog:
            sections.append(
                PromptSection(
                    name="available-skills",
                    source="skill-registry",
                    priority=600,
                    cacheable=False,
                    content=f"# Available Skills\n\n{skill_catalog}",
                )
            )
        if bkn_catalog:
            sections.append(
                PromptSection(
                    name="available-bkns",
                    source="bkn-registry",
                    priority=650,
                    cacheable=False,
                    content=bkn_catalog,
                )
            )
        if error_history:
            sections.append(
                PromptSection(
                    name="recoverable-errors",
                    source="agent-runtime",
                    priority=900,
                    cacheable=False,
                    content="# Recoverable Errors\n\n" + "\n".join(error_history),
                )
            )
        return sections

    def _model_capabilities(self) -> ModelCapabilities:
        """Return active model capabilities, preserving legacy defaults when unset."""
        if self.model_config is None:
            return ModelCapabilities()
        return self.model_config.capabilities

    @staticmethod
    def _build_capabilities_section(model_config: ModelConfig) -> str:
        """Render concise capability facts that affect model behavior."""
        capabilities = model_config.capabilities
        lines = [
            "# Model Capabilities",
            f"- Provider: `{model_config.provider}`",
            f"- Prompt Profile: `{model_config.prompt_profile}`",
            f"- Model Type: `{model_config.model_type}`",
            f"- Tool Calling: {'enabled' if capabilities.tool_calling else 'disabled'}",
            f"- JSON Schema: {'enabled' if capabilities.json_schema else 'disabled'}",
            f"- Vision: {'enabled' if capabilities.vision else 'disabled'}",
            f"- Max Parallel Tools: {capabilities.max_parallel_tools}",
        ]
        if not capabilities.tool_calling:
            lines.append("- Do not claim to call tools. Answer directly from visible context.")
        elif capabilities.max_parallel_tools <= 1:
            lines.append("- Use at most one tool call in a single assistant turn.")
        return "\n".join(lines)
