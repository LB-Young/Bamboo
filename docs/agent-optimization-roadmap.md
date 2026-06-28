# Bamboo Agent 下一阶段优化路线

本文档用于指导 Bamboo 下一阶段 Agent 能力建设。内容基于当前 Bamboo 代码结构，并参考了 `/Users/liubaoyang/Documents/YoungL/agents` 下几个成熟 Agent 项目的设计：

- Auton：统一 `SessionFactory`、System Prompt 装配、cron/heartbeat 任务设计。
- OpenCode：provider-specific prompt、environment/skills/instructions 组合、结构化输出和多 step 消息转换。
- Claude Code Source：主循环状态管理、内存/技能预取、可恢复错误延迟暴露、prompt cache 保护。
- OpenClaw：embedded runner 的系统提示词参数化、tool result context guard、sandbox/runtime info 注入。
- Hermes Agent：fallback providers、auxiliary model、memory provider、session lifecycle hooks、profile scoped memory。

## 总体判断

Bamboo 现在已经具备基础框架：`TaskFactory -> TaskRuntime -> AgentRuntime -> EventBus -> ToolRegistry -> LLMFactory`，也有 project/chat prompt、上下文压缩、工具调用循环和可恢复错误机制。

下一阶段不应该继续堆单点功能，而应该围绕四个目标增强：

1. 让 Agent 的运行上下文更完整：系统提示词、项目指令、工具、技能、记忆、环境信息一次性装配。
2. 让 Agent 的执行更稳定：工具结果预算、错误恢复、fallback model、任务级持久化。
3. 让 Agent 的能力更可扩展：skills/subagents/workflows/MCP 统一进入运行时。
4. 让 Agent 的效果可评估：事件轨迹、测试脚本、回放、指标和失败样本沉淀。

## 优先级路线

### P0：统一会话构建层，升级 TaskRuntime 初始化边界

参考来源：

- Auton：`auton/gateway/session_factory.py` 把 userspace、session store、LLM、tools、MCP、prompt、skills、subagents、processor 全部集中初始化。
- OpenCode：`packages/opencode/src/session/prompt.ts` 在每次处理前组合 env、skills、instructions 和 model messages。

当前 Bamboo 状态：

- `TaskRuntime` 已经初始化 `LLMFactory`，但 tools、prompt、memory、skills、subagents、MCP 的装配分散。
- `SessionFactory` 只负责创建 `Session` 和基础 system prompt。
- `AgentRuntime` 直接持有 `ToolRegistry`、`AgentPromptBuilder`、`ContextCompactor`，后续能力继续增加会让构造函数越来越重。

建议设计：

新增 `bamboo/runtime/session_runtime.py` 或 `bamboo/runtime/runtime_context.py`，定义统一运行上下文：

```python
@dataclass(slots=True)
class RuntimeContext:
    task: Task
    session: Session
    llm_factory: LLMFactory
    tool_registry: ToolRegistry
    prompt_builder: AgentPromptBuilder
    memory_manager: MemoryManager | None
    skill_registry: SkillRegistry | None
    subagent_registry: SubagentRegistry | None
    event_bus: EventBus
```

落地步骤：

1. 保持 `TaskFactory` 只创建 Task，不扩展执行逻辑。
2. 在 `TaskRuntime` 内新增 `_build_runtime_context(task)`。
3. 把 `ToolRegistry`、`AgentPromptBuilder`、`ContextCompactor` 的创建从 `AgentRuntime.__init__` 上移到 `TaskRuntime` 或 `RuntimeContextBuilder`。
4. `AgentRuntime` 构造函数只接收 `RuntimeContext` 和少量策略对象。
5. 文档明确边界：Factory 创建数据对象，RuntimeContext 创建运行依赖，AgentRuntime 只执行 OTA 循环。

验收标准：

- `AgentRuntime.__init__` 参数减少到 3-5 个核心参数。
- CLI、测试脚本、未来 Web 入口都复用同一套 RuntimeContext 初始化。
- 新增工具、技能、记忆时不需要修改多个入口。

### P0：System Prompt 装配升级为可插拔 Section Pipeline

参考来源：

- Auton：`SystemPromptBuilder` 支持静态层、动态环境、项目指令、记忆、skills、subagents、MCP 按优先级拼接。
- OpenCode：`SystemPrompt.provider(model)` 根据模型族选择不同 prompt，`environment(model)` 注入模型、cwd、worktree、git、平台、日期。
- Claude Code Source：`buildEffectiveSystemPrompt` 支持 default、custom、agent、append、override 的优先级。
- OpenClaw：`buildEmbeddedSystemPrompt` 接收 runtimeInfo、tools、skillsPrompt、sandboxInfo、contextFiles、workspaceNotes 等参数。

当前 Bamboo 状态：

- 已有 `bamboo/prompts/{project,chat,shared}/*.md`。
- 运行时优先读取 `~/.bamboo/prompts`，包内作为 fallback。
- 目前动态信息只有 runtime environment 和项目指令文件，缺少 tools/skills/subagents/memory/MCP/provider-specific sections。

建议设计：

将 `SystemPromptBuilder` 改成 section pipeline：

```python
@dataclass(slots=True)
class PromptSection:
    name: str
    priority: int
    source: str
    content: str
    cacheable: bool = True
```

建议 section 顺序：

1. `00_identity`：project/chat 身份。
2. `10_core_rules`：通用规则。
3. `20_runtime_environment`：cwd、project_root、OS、shell、date、git root、model/provider。
4. `30_project_instructions`：`BAMBOO.md`、`AGENTS.md`、`CLAUDE.md`。
5. `40_memory`：项目记忆、用户偏好、历史摘要。
6. `50_tools`：工具目录和使用纪律。
7. `60_skills`：可用 skill 摘要，必要时按需加载完整内容。
8. `70_subagents`：可委派 subagent 列表和调用规则。
9. `80_mcp`：MCP server 状态和可用工具。
10. `90_runtime_notes`：恢复错误、压缩摘要、临时系统提醒。

落地步骤：

1. `bamboo/prompts/system_prompt.py` 不再直接返回字符串，而是先构建 `list[PromptSection]`。
2. `AgentPrompt.render()` 输出 section 名称，方便调试。
3. 在 `TaskRuntime` 创建 task 后，把最终 system prompt hash 写入 `task.metadata["system_prompt_hash"]`。
4. 支持 `~/.bamboo/prompts/provider/{deepseek,gpt,claude,minimax}/*.md`，对不同模型平台注入兼容性提示。
5. prompt 文件缺失时只跳过该 section，不让会话启动失败。

验收标准：

- 打印 debug prompt 时能看到每个 section 的来源和优先级。
- 修改 `~/.bamboo/prompts` 后，下次任务立即生效。
- project/chat 两种模式共享基础 section，但身份、工具主动性和代码执行纪律不同。

### P0：工具结果上下文预算和截断机制

参考来源：

- OpenClaw：`tool-result-context-guard.ts` 给单个 tool result 和整体 tool result context 设置预算，超限时截断或替换旧输出。
- Claude Code Source：query loop 中会 withheld recoverable errors，避免 prompt-too-long 直接污染用户输出，并尝试 reactive compact。

当前 Bamboo 状态：

- `ContextCompactor` 会压缩旧消息，但没有单独限制工具结果。
- 如果 `read/grep/bash` 返回大量内容，可能一次 tool result 就撑爆上下文。
- `ToolResultEvent` 和 session tool message 写入的是完整输出。

建议设计：

新增 `bamboo/runtime/tool_result_budget.py`：

```python
@dataclass(slots=True)
class ToolResultBudgetPolicy:
    max_single_result_tokens: int
    max_total_result_tokens: int
    truncation_notice: str = "[truncated: tool output exceeded context budget]"
```

落地步骤：

1. 在 `_execute_tool_call` 写入 session 前，对 `result.content` 做预算处理。
2. 单个 tool result 超限时保留头尾或按行截断，附带截断说明。
3. 历史 tool result 总量超限时，把最旧 tool result 替换为 `[compacted: old tool output removed]`。
4. `ToolResultEvent` 可以保留完整输出或截断输出需要分清：建议事件给 UI 全量，session 给模型截断版。
5. `Message` 增加 `metadata` 字段记录 `original_length`、`truncated`、`budget_policy`。

验收标准：

- `bash` 输出 100k 字符时不会导致下一轮模型请求爆上下文。
- 模型能看到明确的截断提示。
- 用户 UI 仍能看到完整工具输出，或者至少能看到输出已截断及原始长度。

### P0：工具权限和危险操作审批

参考来源：

- OpenCode：`Permission.disabled(["skill"], agent.permission)` 控制能力可见性。
- Auton：SessionFactory 中按 permission mode 初始化工具。
- Hermes Agent：release notes 中强调 approval session key isolation、active-session guard、cross-session isolation。

当前 Bamboo 状态：

- `RunParams` 已有 `permission`、`yes_all`，但内置工具执行还没有完整审批层。
- `bash/write/edit` 等工具可以被模型直接调用，缺少风险分级。

建议设计：

新增 `bamboo/security/permission_policy.py`：

```python
class PermissionDecision(str, Enum):
    allow = "allow"
    ask = "ask"
    deny = "deny"

@dataclass(slots=True)
class PermissionRequest:
    tool_name: str
    arguments: dict
    risk_level: str
    reason: str
```

落地步骤：

1. `ToolRegistry` 中为每个工具增加 `risk_level`：read-only、write、execute、network、destructive。
2. `AgentRuntime._execute_tool_call` 前调用 `PermissionPolicy.evaluate(tool_call, run_params)`。
3. `EventBus` 增加 `PermissionRequestEvent`、`PermissionResultEvent`。
4. CLI adapter 收到 ask 时请求用户确认；`--yes` 跳过 ask；高危操作即使 yes 也可配置必须确认。
5. 对 `bash` 做命令分类：只读命令、写文件命令、删除命令、网络命令、git 破坏性命令。

验收标准：

- `read/glob/grep` 默认直接允许。
- `write/edit/bash` 根据权限模式 ask 或 allow。
- `rm -rf`、`git reset --hard`、`git push --force` 默认 deny 或强确认。
- 每个审批都有 session_id/task_id/tool_call_id，不能跨 session 复用。

### P1：模型调用可靠性、Fallback 和 Auxiliary Model

参考来源：

- Hermes Agent：primary fallback model，失败时原地替换 client，且每个 session 最多 fallback 一次。
- Hermes Agent：auxiliary tasks 包括 compression、vision、web_extract、session_search、skills_hub、memory_flush，有独立 provider chain。
- Claude Code Source：对 prompt-too-long、max-output-tokens 等 recoverable errors 延迟暴露并尝试恢复。

当前 Bamboo 状态：

- `models.yaml` 支持多个 provider。
- `bamboo_main_agent.yaml` 支持 `model` 和 `compaction_model`。
- 缺少主模型 fallback、辅助任务模型分组、错误类型分级。

建议设计：

扩展 `models.yaml`：

```yaml
default_model: deepseek-chat

agents:
  main:
    model: deepseek-chat
    fallback_model: gpt-default
  compaction:
    model: gpt-default
    fallback_model: deepseek-chat
  skills_hub:
    model: deepseek-chat
  memory:
    model: deepseek-chat
```

落地步骤：

1. `LLMResponseError` 增加错误分类：rate_limit、auth、server_error、not_found、timeout、invalid_response、context_length、max_output。
2. `AgentRuntime._think` 捕获可 fallback 错误，调用 `LLMRouter.switch_to_fallback()`。
3. session 级别记录 `fallback_used=true`，防止无限 fallback。
4. compaction、memory、skill search 不再复用 main agent 逻辑，而是通过 `AuxiliaryModelRouter` 取模型。
5. 对 context length 错误做 reactive compact：先压缩，再重试同一轮模型调用。

验收标准：

- 主模型 429/5xx 后可切换 fallback 并继续同一 session。
- auth 错误不盲目重试，直接 fallback 或失败。
- fallback 只发生一次，失败后清晰报错。
- compaction 模型不可用时可以回退到 main model，或降级为裁剪旧消息。

### P1：Session Store 和可回放执行轨迹

参考来源：

- Auton：SessionStore 区分 project/date 模式。
- Hermes Agent：session lifecycle hooks、session commit、shared thread sessions。
- OpenCode：session messages 在每个 step 中转换为 model messages，并保存 finish/error。

当前 Bamboo 状态：

- 有 `InMemoryTaskStore`，但任务和消息缺少稳定持久化。
- 多轮测试依赖真实运行过程，缺少可回放轨迹。

建议设计：

新增持久化目录：

```text
~/.bamboo/sessions/
  projects/{project_hash}/{session_id}/
    session.json
    messages.jsonl
    events.jsonl
    tasks.jsonl
  dates/{yyyy-mm-dd}/{session_id}/
```

落地步骤：

1. 实现 `SessionStore`：append-only 写 messages/events/tasks。
2. `EventBus` 增加 event recorder 订阅器，所有事件写入 `events.jsonl`。
3. 每次 LLM request/response 记录脱敏后的 request metadata：model、provider、token estimate、tool_count、finish_reason。
4. 增加 `bamboo run --resume <session_id>`。
5. 增加 `bamboo replay <session_id>` 用于调试 message 构造和工具循环。

验收标准：

- 任务中断后可以恢复 session。
- 任意一次失败可以通过 events/messages 重建执行链路。
- 测试可以使用 fixture replay，不必每次真实调用模型。

### P1：Memory Manager 和项目/用户记忆

参考来源：

- Hermes Agent：external memory provider 会注入上下文、每轮预取、响应后同步、session end 提取、增加 memory tools。
- Auton：SystemPromptBuilder 读取 Project Memory 和 Today Memory。
- Claude Code Source：相关 memory prefetch 在主循环开始后后台执行，避免阻塞模型调用链路。

当前 Bamboo 状态：

- `bamboo/memory/get_memory_path.py` 只有路径划分。
- prompt 目前没有注入项目记忆、用户偏好、历史任务摘要。
- 当前设想中的完整对话 `jsonl` 更适合作为事实底账，不适合直接作为每次 query 的首选检索层。

建议设计：

Memory Manager 应分成两层：

1. 源日志层：完整保存每轮对话、工具调用和事件，使用 `jsonl` 作为不可丢失的原始记录。
2. 知识抽象层：把源日志中稳定、有复用价值的信息抽象为一组可读、可编辑、可检索的 `md` 文件。

project 模式和 chat 模式的知识边界应该不同：

```text
~/.bamboo/memory/
  chat/
    knowledge/
      profile.md
      preferences.md
      recurring_topics.md
      decisions.md
      open_questions.md
    sessions/
      {date}/{session_id}/messages.jsonl

  projects/
    {project_hash}/
      knowledge/
        overview.md
        architecture.md
        decisions.md
        coding_style.md
        bugs_and_fixes.md
        workflows.md
        open_questions.md
      sessions/
        {session_id}/messages.jsonl
```

其中：

- project 模式：每个项目维护独立 knowledge，不污染其他项目。
- chat 模式：共享一套全局 chat knowledge，用来保存用户偏好、长期主题、跨项目但非项目专属的信息。
- `jsonl` 只负责完整保存源对话，不直接作为主 prompt 长期上下文。
- `md` knowledge 是 Agent 优先读取和检索的长期知识层。

新增 `bamboo/memory/manager.py`：

```python
class MemoryManager:
    def load_prompt_context(self, task: Task) -> str: ...
    async def search_knowledge(self, query: str, scope: MemoryScope) -> MemoryContext: ...
    async def search_source_logs(self, query: str, scope: MemoryScope) -> MemoryContext: ...
    async def write_source_turn(self, session: Session, messages: list[Message]) -> None: ...
    async def update_knowledge_after_turn(self, task: Task, turn: ConversationTurn) -> None: ...
    async def finalize_session(self, session: Session) -> None: ...
```

新增一个专用 `MemoryAbstractionAgent` 或 `KnowledgeSubagent`：

```python
class KnowledgeSubagent:
    async def extract_updates(self, turn: ConversationTurn, current_files: KnowledgeFiles) -> KnowledgePatch: ...
    async def apply_updates(self, patch: KnowledgePatch) -> None: ...
```

它不参与用户主任务回答，只在每轮对话结束后运行，负责把刚刚的完整 turn 抽象成稳定知识，并更新对应 `md` 文件。

KnowledgeSubagent 的输入：

- 本轮用户消息。
- 本轮 assistant 最终回复。
- 本轮工具调用和关键工具结果摘要。
- 本轮新增/修改文件列表。
- 当前 scope 下已有的 knowledge md 文件内容。

KnowledgeSubagent 的输出：

- 哪些知识文件需要更新。
- 每个文件的结构化 patch 或完整新内容。
- 本轮不需要沉淀的原因。
- 可选：需要回源 jsonl 的线索。

建议的抽象原则：

- 只沉淀稳定事实、用户偏好、项目约束、架构决策、反复出现的问题和未完成事项。
- 不沉淀一次性闲聊、临时命令输出、明显过期的信息。
- 不把工具输出原文大段搬进 md，只保留结论、路径、决策和可追溯线索。
- 对不确定内容要标注来源 session_id/task_id，避免知识污染。

检索链路：

```text
new query
  -> resolve memory scope
  -> search knowledge md files
  -> if enough: inject relevant knowledge into context
  -> if not enough: search source jsonl logs
  -> if source logs found: inject snippets and optionally ask KnowledgeSubagent to backfill md
```

这条链路的关键点是：`md knowledge` 是首选上下文，`jsonl` 是回源依据。这样既保留完整历史，又避免每次都在原始对话日志里做低层检索。

落地步骤：

1. 先实现完整源日志保存：project/chat 分别把每轮 `messages.jsonl`、`events.jsonl`、`tool_calls.jsonl` 写清楚。
2. 实现 memory scope 解析：project 模式用 project hash，chat 模式用全局 chat scope。
3. 建立 knowledge md 文件骨架：project 和 chat 使用不同模板。
4. 每轮对话结束后触发 `KnowledgeSubagent`，读取本轮完整 turn，生成 knowledge patch。
5. patch 应先写临时文件并校验，再原子替换 md，避免写坏知识库。
6. query 进入 Agent 前先调用 `search_knowledge()`，把命中的 md 段落注入 prompt。
7. 如果 md 命中不足，再调用 `search_source_logs()` 查 jsonl，并把命中的原始片段作为补充上下文。
8. 如果 jsonl 回源命中高价值信息，但 md 没有记录，异步触发一次 knowledge backfill。
9. 增加 memory tools：`memory_read`、`memory_search`、`memory_update`、`memory_backfill_from_logs`。
10. 后续再接 vector/chromadb 或外部 provider，但接口仍以 knowledge layer 为第一入口。

验收标准：

- 用户让 Bamboo 记住偏好后，下次 session 可以在 prompt 中看到。
- project 模式只读取对应项目记忆，不污染其他项目。
- chat 模式读取用户级记忆和当天摘要。
- 每轮结束后会生成或更新对应 scope 的 md knowledge 文件。
- 新 query 需要历史信息时，默认先命中 md knowledge；md 不足时才检索 jsonl 源日志。
- md knowledge 中的关键事实能追溯到 session_id/task_id 或源日志位置。
- 删除或修正 md knowledge 后，下一轮 query 立即使用新的抽象知识。

### P1：Skills Hub 和按需技能加载

参考来源：

- OpenCode：system prompt 中给 skill 列表和描述，真实 skill 通过 tool 按需加载。
- Auton：SkillRegistry 会把技能摘要和部分完整 `SKILL.md` 注入 prompt。
- Claude Code Source：skill discovery prefetch 在主循环中异步启动。

当前 Bamboo 状态：

- 已有 `bamboo/skills/buildin/skill-creator`。
- 缺少统一 SkillRegistry、skill schema、skill load tool、skill 匹配机制。

建议设计：

Skill 文件结构：

```text
~/.bamboo/skills/{skill_name}/
  SKILL.md
  config.yaml
  scripts/
```

落地步骤：

1. 实现 `SkillRegistry`：扫描 buildin + userspace skills，读取 frontmatter/name/description。
2. System Prompt 只注入 skill 摘要列表，避免上下文过大。
3. 新增 `skill_load` tool：按名称读取完整 `SKILL.md` 注入当前 session。
4. 新增 `SkillSelector`：根据用户请求和 skill 描述做轻量匹配，匹配结果放入 prompt。
5. 对 skill 使用情况做 telemetry：触发次数、成功率、耗时。

验收标准：

- 用户请求符合 skill 描述时，模型能知道可用 skill。
- 加载完整 skill 后，后续工具调用遵循 skill 指令。
- skill 目录新增/修改后下一次任务生效。

### P1：Subagent 和委派模型

参考来源：

- Hermes Agent：subagent sessions linked to parent and hidden from session list。
- OpenClaw：embedded runner 支持 agentId、workspaceNotes、runtimeInfo、tools、contextFiles。
- Claude Code Source：主线程 agent 和 custom agent system prompt 有明确优先级。

当前 Bamboo 状态：

- 有 `subagents` 目录结构和配置文件，但 runtime 未真正使用。
- 主 Agent 只有一个 `AgentRuntime`。

建议设计：

新增 `SubagentRuntime` 和 `SubagentRegistry`：

```yaml
subagents:
  code-reviewer:
    description: "审查代码风险和测试缺口"
    model: deepseek-chat
    tools: [read, grep, glob]
    prompt: prompts/subagents/code-reviewer.md
```

落地步骤：

1. `SubagentRegistry` 扫描 buildin 和 userspace subagents。
2. 新增 `subagent_run` tool，由主 Agent 调用。
3. subagent 有独立 session_id，但 metadata 记录 parent_session_id、parent_task_id。
4. subagent 默认只读工具，写操作需要显式配置。
5. subagent 输出结构：summary、findings、files_touched、confidence。

验收标准：

- 主 Agent 可以委派“搜索代码”“代码审查”“测试生成”等任务。
- subagent 结果以 tool result 形式回到主 Agent。
- subagent 失败不直接失败主任务，而是反馈错误供主 Agent 决策。

### P1：事件系统升级为可观测 Agent Trace

参考来源：

- Auton：EventBus 让 CLI/Web 订阅 text/tool/compact 等事件。
- Hermes Agent：MCP bridge 提供 events_poll/events_wait/permissions_list_open。
- Claude Code Source：query loop yield 多种事件，包括 stream_request_start、tool use、recovery。

当前 Bamboo 状态：

- `EventBus` 已有基础事件。
- 缺少标准 trace schema、事件持久化、事件订阅过滤。

建议设计：

统一事件分类：

```text
task.*         task.created/running/completed/failed
agent.*        state.changed/iteration.started/recovered
llm.*          request.started/response.finished/error/fallback
tool.*         call/result/error/permission
context.*      compact.started/compact.finished/budget
memory.*       prefetch/write/finalize
skill.*        selected/loaded
subagent.*     started/finished/error
```

落地步骤：

1. 所有事件继承统一 BaseEvent：event_id、timestamp、session_id、task_id、parent_event_id。
2. EventBus 支持 subscribe(pattern)。
3. 增加 `TraceRecorder` 写入 `events.jsonl`。
4. CLI 增加 `--debug-events` 打印事件流。
5. docs 中维护事件 schema。

验收标准：

- 一次任务可以从 events.jsonl 完整还原：用户输入、模型调用、工具调用、压缩、最终输出。
- UI 可以只订阅 text/tool，不需要关心内部状态。

### P2：Reactive Compact 和多级上下文治理

参考来源：

- Claude Code Source：遇到 prompt-too-long 时 withheld 错误，尝试 reactive compact 后继续。
- OpenClaw：工具结果先做 context guard，再进入模型上下文。
- Hermes Agent：compression 有独立 auxiliary provider，失败时可降级。

当前 Bamboo 状态：

- 已有 preemptive compact：达到 50% 或剩余 20k tokens 时压缩。
- 没有捕获模型返回的 context length error 后再压缩重试。

建议设计：

上下文治理分层：

1. 写入时治理：tool result budget。
2. 请求前治理：preemptive compact。
3. 请求失败治理：reactive compact。
4. 压缩失败治理：drop oldest low-value messages。

落地步骤：

1. LLM provider 抛出 `ContextLengthError`。
2. `_think` 捕获后触发强制 compact：`ContextCompactor.compact(force=True)`。
3. compact 后最多重试一次同一轮模型请求。
4. 如果 compact 无收益，则丢弃最旧工具结果或旧 assistant 输出。
5. 写入 `SessionCompactEvent` 的 reason：preemptive/reactive/manual。

验收标准：

- prompt too long 不直接失败任务。
- reactive compact 后模型能继续回答。
- compact 失败也有明确降级路径。

### P2：工作流、Cron 和 Heartbeat

参考来源：

- Auton cron：`jobs.yaml` 支持 schedule、session、delivery、retry；main-session 和 isolated 两种执行模式。
- Hermes Agent：cron/path traversal hardening、session lifecycle hooks。

当前 Bamboo 状态：

- 有 workflow 目录和配置，但 runtime 未接入。
- 没有定时任务、后台心跳、任务队列。

建议设计：

先实现轻量 workflow，再实现 cron：

```yaml
workflows:
  daily-review:
    steps:
      - agent: main
        prompt: "总结今天项目变化"
      - tool: write
        args:
          file_path: "daily.md"
```

Cron 配置：

```yaml
jobs:
  - name: daily-report
    schedule: "0 9 * * *"
    session: isolated
    prompt: "生成昨日项目报告"
    retry:
      max_attempts: 3
      backoff: exponential
```

落地步骤：

1. `WorkflowRunner` 支持顺序步骤、失败策略、变量传递。
2. `CronScheduler` 读取 `~/.bamboo/cron/jobs.yaml`。
3. `session=isolated` 创建新 Task；`session=main` 写入主会话系统事件。
4. 增加 retry/backoff 和 logs jsonl。
5. cron 执行必须走权限策略，不能绕过工具审批。

验收标准：

- 可配置定时任务并产生执行日志。
- 失败按指数退避重试。
- 用户可以禁用/启用 job。

### P2：Provider-specific Prompt 和模型能力注册

参考来源：

- OpenCode：不同模型族使用不同 provider prompt。
- Claude Code Source：不同 agent/custom prompt 和 append prompt 有明确优先级。

当前 Bamboo 状态：

- provider 客户端已拆分：deepseek、minimax、gpt、claude。
- prompt 对模型平台没有差异化。

建议设计：

扩展 `models.yaml`：

```yaml
models:
  deepseek-chat:
    provider: deepseek
    capabilities:
      tool_calling: true
      json_schema: false
      vision: false
      max_parallel_tools: 1
    prompt_profile: deepseek
```

落地步骤：

1. `ModelConfig` 增加 `capabilities` 和 `prompt_profile`。
2. prompt builder 加载 `prompts/provider/{profile}/*.md`。
3. Tool calling 序列化根据 capabilities 调整：不支持 tools 的模型走文本协议 fallback。
4. Claude provider 加入 tool_use block 的专用提示；OpenAI-compatible 加入 function calling 格式提示。

验收标准：

- 不同模型能加载不同兼容提示。
- 不支持 tool calling 的模型也有清晰降级路径。

## 建议实施顺序

第一阶段（先稳住主循环）：

1. RuntimeContext 统一构建。
2. Prompt Section Pipeline。
3. Tool Result Budget。
4. Permission Policy。
5. 基础 SessionStore + events.jsonl。

第二阶段（提升效果）：

1. MemoryManager。
2. SkillRegistry + skill_load。
3. Reactive Compact。
4. Fallback Model + Auxiliary Model。
5. Provider-specific Prompt。

第三阶段（扩展生态）：

1. SubagentRuntime。
2. WorkflowRunner。
3. Cron/Heartbeat。
4. MCP 接入。
5. 评估与回放工具。

## 当前 Bamboo 模块对应改造点

| Bamboo 模块 | 建议改造 |
|---|---|
| `bamboo/runtime/task_runtime.py` | 上移 RuntimeContext 构建，集中初始化 tools/prompt/memory/skills/subagents |
| `bamboo/runtime/agent_runtime.py` | 保持 OTA 主循环，增加 permission、tool budget、fallback、reactive compact |
| `bamboo/runtime/prompt.py` | 接入 PromptSection，不只拼 system/tool/error |
| `bamboo/prompts/system_prompt.py` | 从字符串 builder 升级为 section pipeline |
| `bamboo/runtime/context_compactor.py` | 支持 force compact、reason、fallback compaction |
| `bamboo/tools/registry.py` | 增加 risk_level、enabled、source、schema version |
| `bamboo/factory/session.py` | 接入 SessionStore 后避免只创建内存 Session |
| `bamboo/factory/event_bus.py` | 增加 pattern subscribe 和 TraceRecorder |
| `bamboo/llms/factory.py` | 增加 LLMRouter、fallback、auxiliary model resolution |
| `bamboo/memory/` | 从路径工具升级为 MemoryManager |
| `bamboo/skills/` | 增加 SkillRegistry 和 skill_load tool |
| `bamboo/subagents/` | 增加 SubagentRegistry 和 SubagentRuntime |

## 不建议现在做的事

- 不要先做复杂 UI。当前最缺的是 runtime 稳定性、上下文治理和可观测性。
- 不要马上接很多外部 memory provider。先把本地 memory manager 的接口和生命周期打稳定。
- 不要让 subagent 直接拥有写权限。先默认只读，等权限策略完善后再放开。
- 不要把所有 skill 全文塞进 system prompt。应该先摘要，按需加载全文。
- 不要让 fallback 无限链式切换。每个 session 最多一次主 fallback，auxiliary 可独立 fallback。

## 下一步最小任务拆分

建议下一轮从以下 5 个 PR/任务开始：

1. `RuntimeContextBuilder`：把 `TaskRuntime._create_agent` 里的依赖创建集中化。
2. `PromptSection`：让 system prompt builder 输出 section 列表，并在 debug 中可见。
3. `ToolResultBudget`：限制工具结果进入 session 的上下文体积。
4. `PermissionPolicy`：为 bash/write/edit 加审批事件和 CLI 确认。
5. `SessionStore`：落地 messages.jsonl/events.jsonl，支持最小 replay。

这 5 项完成后，Bamboo 的 Agent 框架会从“能跑通”进入“可调试、可恢复、可扩展”的阶段。
