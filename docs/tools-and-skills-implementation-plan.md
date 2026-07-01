# Bamboo Tools and Skills 实现方案

本文档基于对 `/Users/liubaoyang/Documents/YoungL/agents` 下 OpenClaw、OpenCode、Claude Code Source、Hermes Agent、Auton 等项目的横向阅读，给 Bamboo 设计下一阶段 tools、skills、subagents、MCP 和安全能力的实现方案。

## 背景判断

Bamboo 当前已有主链路：

```text
TaskFactory -> TaskRuntime -> AgentRuntime -> RuntimeContextBuilder
           -> ToolRegistry -> LLMFactory -> EventBus
```

工具层已有 `read/write/edit/glob/grep/bash/skill_load`，SkillRegistry 也已有扫描、索引、校验、状态、usage 记录。但相比其他项目，Bamboo 缺少：

- 工具能力：MCP、web、task、todo、git、LSP、batch、apply_patch/multiedit。
- 安全能力：命令风险分类、权限审批、沙箱、审计、输出脱敏。
- Skill 内容：内置 skill 太少，缺开发工作流类 skill。
- Skill 生态：Hub、安装前扫描、trust level、lockfile。
- 子 Agent：目录和配置是空壳，缺 task/subagent runtime。
- 本地模型体验：已支持 Ollama/vLLM 调用，但缺模型发现和配置向导。

设计原则：

1. 优先复用 Bamboo 现有 Python 架构，不引入 TypeScript 插件运行时。
2. 能从 Auton/Hermes 直接借 Python 结构的优先落地。
3. OpenCode/Claude/OpenClaw 的 TypeScript/Rust 实现只借设计，不照搬代码。
4. 新能力全部走现有主链路，避免绕开 `TaskRuntime` 和 `EventBus`。
5. 安全能力先做可审计、可拦截，再做强沙箱。

## 参考来源

### Auton

最适合直接参考 Bamboo 的 Python 工具实现：

- `auton/tools/registry.py`：更完整的 ToolRegistry，支持 source、enabled、blocked、MCP client 管理。
- `auton/tools/mcp/__init__.py`：stdio MCP client 原型。
- `auton/tools/bash/security.py`：命令分类和危险命令检测。
- `auton/tools/bash/sandbox.py`：macOS sandbox-exec、Linux bwrap/unshare 原型。
- `auton/tools/task_create` 等：后台任务工具。

### Hermes Agent

最适合参考 skill、安全和 MCP 的成熟形态：

- `tools/skills_tool.py`：progressive disclosure、platform/prerequisite 检查。
- `tools/skills_guard.py`：外部 skill 安装前安全扫描。
- `tools/skills_hub.py`：多来源 skill hub、quarantine、lockfile。
- `skills/software-development/*`：可直接迁移的开发工作流 skills。
- `skills/mcp/native-mcp/SKILL.md`：更成熟的 MCP 目标形态。
- `tools/tirith_security.py`：内容级安全扫描理念。

### OpenCode

适合参考 Agent 工具产品形态：

- `packages/opencode/src/tool/task.ts`：子 Agent 工具、权限收窄、session 复用。
- `packages/opencode/src/tool/todo.ts`：TodoWrite 工具。
- `packages/opencode/src/tool/batch.ts`：并行工具调用。
- `packages/opencode/src/tool/lsp.ts`：LSP code intelligence。
- `packages/opencode/src/tool/skill.ts`：动态列出并加载 skill。
- `.opencode/command/*.md`：轻量 custom commands。

### Claude Code Source

适合参考安全和专业 Agent 模式：

- `src/tools/BashTool/*`：权限、危险命令、路径校验。
- `src/tools/TodoWriteTool`：任务计划状态。
- `src/tools/AgentTool`：内置专业子 Agent。
- `src/tools/MCPTool`、`ListMcpResourcesTool`、`ReadMcpResourceTool`：MCP 资源访问。
- `utils/sandbox`、`utils/permissions`：分层安全设计。

### OpenClaw

适合参考生态和配置向导：

- `extensions/ollama/index.ts`：本地模型发现、选择时 pull model。
- `extensions/vllm/index.ts`：OpenAI-compatible self-hosted provider 配置向导。
- `extensions/diffs`：复杂能力以 extension + skill + asset 组合分发。
- Tool Profile / Plugin manifest / installer metadata：适合 Bamboo 未来 plugin 化。

## 总体架构

建议把下一阶段拆成四层：

```text
Model Layer
  - provider 调用
  - 本地模型发现
  - fallback / auxiliary model

Runtime Layer
  - TaskRuntime
  - AgentRuntime
  - RuntimeContextBuilder
  - EventBus

Tool Layer
  - ToolRegistry
  - built-in tools
  - MCP-discovered tools
  - PermissionPolicy
  - AuditLog

Skill Layer
  - SkillRegistry
  - SkillLoadTool
  - SkillHub
  - SkillGuard
  - built-in skills
```

核心方向：工具和 skill 都必须变成运行时可观察对象，所有执行、加载、拦截、失败都发事件并可追踪。

## Phase 0：工具注册表和权限基座

### 目标

先扩展 Bamboo 当前 `ToolRegistry`，为后续 MCP、task、web、todo、安全审批打基础。

### 设计

扩展 [bamboo/tools/registry.py](/Users/liubaoyang/Documents/YoungL/agents/Bamboo/bamboo/tools/registry.py)：

```python
@dataclass(slots=True)
class ToolMetadata:
    source: str                         # builtin | mcp:<server> | plugin:<name> | project
    enabled: bool = True
    blocked: bool = False
    risk_level: str = "read"            # read | write | execute | network | destructive
    tags: list[str] = field(default_factory=list)
```

新增能力：

- `block(name)` / `unblock(name)`
- `list_by_source(source_prefix)`
- `get_metadata(name)`
- `register_mcp_tools(server, tools)`
- `set_mcp_client(server, client)`
- `get_mcp_client(server)`

### 文件

- 修改 `bamboo/tools/registry.py`
- 修改 `bamboo/tools/buildin/base.py`，给 `Tool` 增加默认 `risk_level`
- 修改 `bamboo/tools/buildin/__init__.py`，注册新增内置工具
- 新增测试 `tests/test_tool_registry.py` 覆盖 source、block、risk metadata

### 验收

- 原有工具 schema 输出不变。
- 禁用/阻塞工具后，模型不可再调用。
- 工具摘要能显示来源和 risk_level。

## Phase 1：Todo 和 Task 工具

### 目标

先补低成本高收益工具，让 Agent 能管理长任务状态，并为子 Agent 做铺垫。

### TodoWriteTool

参考 OpenCode `todowrite` 和 Claude Code `TodoWriteTool`。

新增 `bamboo/tools/buildin/todo.py`：

```python
class TodoWriteTool(Tool):
    name = "todo_write"
    risk_level = "write"
```

输入：

```json
{
  "todos": [
    {"id": "1", "content": "...", "status": "pending|in_progress|completed"}
  ]
}
```

存储策略：

- 初期写入 `task.metadata["todos"]`，并发 `TodoUpdateEvent`。
- 后续迁移到 SessionStore，支持 Web UI 恢复。

### Task Tools

新增：

- `task_create`
- `task_get`
- `task_list`
- `task_stop`

初期只做进程内任务记录，复用 `TaskStore`；后续接入持久化。

建议 `TaskSnapshot` 增加：

```python
title: str
created_at: str
updated_at: str
metadata: dict[str, str]
```

### 文件

- 新增 `bamboo/tools/buildin/todo.py`
- 新增 `bamboo/tools/buildin/task.py`
- 修改 `bamboo/runtime/store.py`
- 修改 `bamboo/helpers/constant.py` 增加 todo/task 事件
- 补测试 `tests/test_task_tools.py`、`tests/test_todo_tool.py`

### 验收

- 模型能调用 `todo_write` 更新任务计划。
- `task_create/list/get` 能看到当前进程任务。
- `task_stop` 至少能标记取消，不要求第一版真实中断 asyncio task。

## Phase 2：MCP 接入

### 目标

支持 stdio MCP server，并把 MCP tools 注册成原生 Bamboo tools。

### 两阶段实现

第一阶段：代理工具，低风险快速可用。

```text
mcp(server, tool, arguments)
```

第二阶段：原生注册，更适合模型使用。

```text
mcp_github_list_issues(...)
mcp_filesystem_read_file(...)
```

建议直接按第二阶段设计，但实现上可先保留代理工具作为 fallback。

### 配置

新增 `bamboo/configs/mcp.yaml` 和用户空间 `~/.bamboo/configs/mcp.yaml`：

```yaml
mcp:
  auto_start: true
  servers:
    github:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
      timeout: 120
      connect_timeout: 60
```

### 安全

借 Hermes 的做法：

- stdio server 默认只继承安全环境变量：`PATH/HOME/USER/LANG/LC_ALL/TERM/SHELL/TMPDIR`
- 只有配置里显式写入的 env 才传给 MCP server。
- MCP 错误输出进入模型前做 token/secret 脱敏。
- MCP 工具 source 记录为 `mcp:<server>`。

### 文件

- 新增 `bamboo/tools/mcp/client.py`
- 新增 `bamboo/tools/mcp/manager.py`
- 新增 `bamboo/tools/buildin/mcp.py`
- 修改 `RuntimeContextBuilder`，启动时加载 MCP servers 并注册 tools
- 修改 `ToolRegistry` 支持 MCP client lifecycle

### 验收

- 配置一个 stdio MCP server 后，`ToolRegistry.schemas()` 能看到其工具。
- MCP server 不会继承全部 shell 环境。
- MCP 工具失败时错误信息不会泄漏 token。
- MCP server 关闭时进程被回收。

## Phase 3：Bash 安全、权限审批和审计

### 目标

让 `bash/write/edit/mcp/network` 等工具有统一审批和审计。

### PermissionPolicy

新增 `bamboo/security/permission_policy.py`：

```python
class PermissionDecision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"

@dataclass(slots=True)
class PermissionRequest:
    session_id: str
    task_id: str
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    risk_level: str
    reason: str
```

模式：

- `bypass`：全部允许，但仍审计。
- `auto`：read 允许，write/execute ask，destructive deny。
- `deny`：只允许 read。
- `strict`：read 允许，network/execute/write 默认 ask 或 deny。

兼容现有 `RunParams.permission` 和 `RunParams.yes_all`。

### Bash 分类

新增 `bamboo/security/command_security.py`，参考 Auton：

- `READ_ONLY`
- `WRITE`
- `DESTRUCTIVE`
- `NETWORK`
- `UNKNOWN`

第一版只做 pattern matching。后续再拆 shell AST。

危险命令默认 deny：

- `rm -rf /`
- `mkfs`
- `dd ... of=/dev/*`
- `curl|wget | sh`
- fork bomb
- 覆写 `/etc/passwd`、`~/.ssh/authorized_keys`
- `git reset --hard`
- `git push --force`

### 审计日志

新增 `bamboo/security/audit_log.py`：

```json
{
  "timestamp": "...",
  "session_id": "...",
  "task_id": "...",
  "tool": "bash",
  "category": "destructive",
  "decision": "deny",
  "command": "...",
  "duration_ms": 12,
  "returncode": 1
}
```

路径：`~/.bamboo/storage/audit/tools.jsonl`

### 沙箱

沙箱作为后续增强，不阻塞审批层：

- macOS：`sandbox-exec`
- Linux：`bwrap` 优先，`unshare` fallback
- fail-open/fail-closed 可配置，默认开发环境 fail-open + 明确审计

### 文件

- 新增 `bamboo/security/command_security.py`
- 新增 `bamboo/security/permission_policy.py`
- 新增 `bamboo/security/audit_log.py`
- 修改 `AgentRuntime._execute_tool_call`
- 修改 CLI/Web adapter 处理 `PermissionRequestEvent`

### 验收

- `read/glob/grep` 不触发 ask。
- `write/edit/bash` 在 auto 模式触发 ask。
- 危险 bash 命令被 deny。
- 每次工具执行都有 audit log。

## Phase 4：SkillLoad 增强和内置 Skill 库

### 目标

Bamboo 的 SkillRegistry 框架已经可用，下一步先补体验和内容。

### SkillLoad 增强

改造 `skill_load`：

- description 动态列出可用 skills。
- 加载后返回：
  - `# Skill: <name>`
  - `SKILL.md` 内容
  - `Base directory`
  - sampled files：`references/`、`scripts/`、`templates/`、`assets/`
- 如果 name 不存在，返回 available skills 列表。

输出示例：

```xml
<skill_content name="systematic-debugging">
...
<skill_base_dir>file:///...</skill_base_dir>
<skill_files>
<file>references/example.md</file>
</skill_files>
</skill_content>
```

### 内置 Skills

从 Hermes 迁移为 Bamboo 内置 skill，先做通用开发类：

1. `systematic-debugging`
2. `test-driven-development`
3. `writing-plans`
4. `requesting-code-review`
5. `github-pr-workflow`
6. `native-mcp`

迁移要求：

- 保留 `name/description/version/license`。
- 把工具名改为 Bamboo 现有工具名，如 `read_file` 改为 `read`，`terminal` 改为 `bash`。
- 删除或改写 Hermes 专属路径。
- 每个 skill 增加 `metadata.bamboo.tags`。

### 文件

- 修改 `bamboo/tools/buildin/skill_load.py`
- 新增 `bamboo/skills/buildin/<skill>/SKILL.md`
- 修改 `tests/test_skills.py`

### 验收

- `SkillRegistry.render_catalog()` 能列出新增 skills。
- `skill_load("systematic-debugging")` 返回完整内容和 base dir。
- 新增 skill 都通过 `SkillValidator`。

## Phase 5：Skill Hub 和 Skill Guard

### 目标

支持安装外部 skill，但安装前必须扫描和记录来源。

### 目录

```text
~/.bamboo/skills/
  <skill-name>/
    SKILL.md
  .hub/
    quarantine/
    lock.json
    audit.jsonl
    index-cache/
```

### Trust Level

```text
builtin   -> Bamboo 随包 skill，默认可信
trusted   -> 明确 allowlist 的 repo/source
community -> 其他来源
local     -> 用户本地创建
```

### SkillGuard

参考 Hermes `skills_guard.py`，扫描：

- secret exfiltration
- prompt injection
- destructive command
- persistence
- reverse shell/tunnel
- obfuscation/base64/eval
- unsafe path traversal

策略：

```text
builtin:   safe/caution/dangerous 全 allow，但记录
trusted:   safe/caution allow，dangerous block
community: safe allow，caution/dangerous block，除非 --force
local:     safe/caution allow，dangerous ask
```

### SkillHub

第一版只支持 GitHub repo/path：

```text
bamboo skills search <query>
bamboo skills install github:owner/repo/path/to/skill
bamboo skills list
bamboo skills update
```

后续再支持 ClawHub、agentskills.io、Hermes registry。

### 文件

- 新增 `bamboo/skills/guard.py`
- 新增 `bamboo/skills/hub.py`
- 新增 `bamboo/adapters/cli/skills.py` 或扩展 CLI main
- 修改 `SkillStore` 记录 lockfile 来源

### 验收

- 外部 skill 先进入 quarantine。
- 扫描通过后才移动到 active skills。
- `lock.json` 记录 source、commit/hash、installed_at。
- 危险 skill 默认不能安装。

## Phase 6：Commands 系统

### 目标

引入 OpenCode custom commands 的轻量能力，不必把每个流程都做成 skill。

### 格式

目录：

```text
~/.bamboo/commands/*.md
<project>/.bamboo/commands/*.md
bamboo/commands/buildin/*.md
```

frontmatter：

```yaml
---
description: git commit and push
model: optional-model-name
subtask: true
---
```

正文支持：

- `$ARGUMENTS`
- `!` shell interpolation 第一版先不支持，避免安全复杂度。
- 后续可支持受控 `!`，必须走 PermissionPolicy。

### 内置命令候选

- `commit`
- `changelog`
- `learn`
- `issues`
- `rmslop`
- `spellcheck`

### 文件

- 新增 `bamboo/commands/models.py`
- 新增 `bamboo/commands/registry.py`
- 新增 `bamboo/tools/buildin/command_run.py`

### 验收

- `command_run(name, arguments)` 生成一条 user/system message 并继续 Agent。
- command 可绑定 model，但第一版可以只写入 metadata，不实际切模型。
- project command 覆盖 user/global command。

## Phase 7：Subagent Runtime

### 目标

把 Bamboo 空的 `subagents` 能力落地，先做同进程子任务，再做独立 worktree。

### Agent 定义

目录：

```text
~/.bamboo/agents/<name>.yaml
<project>/.bamboo/agents/<name>.yaml
```

示例：

```yaml
name: explorer
description: Read-only codebase exploration agent.
model: ""
tools:
  read: true
  grep: true
  glob: true
  bash: read_only
  write: false
permission: deny_write
```

### Task Tool

参考 OpenCode：

```python
task(
  description: str,
  prompt: str,
  subagent_type: str,
  task_id: str | None = None,
)
```

行为：

- 创建子 session，`parent_id=当前 session_id`
- 子 session 使用收窄后的 ToolRegistry
- 子任务完成后返回：

```xml
<task_result task_id="...">
...
</task_result>
```

第一版不做并行写入隔离。涉及写文件的子 agent 默认禁用，直到 worktree 支持。

### 内置 Agent

- `explorer`：只读搜索和总结。
- `planner`：只读规划。
- `verifier`：只读 + bash 测试命令。
- `reviewer`：代码审查。

### 文件

- 新增 `bamboo/subagents/models.py`
- 新增 `bamboo/subagents/registry.py`
- 新增 `bamboo/runtime/subagent_runtime.py`
- 新增 `bamboo/tools/buildin/task.py` 或扩展 Phase 1 task 工具

### 验收

- 主 Agent 能调用 `task` 委派给 `explorer`。
- 子 Agent 看不到被禁用工具。
- 子 Agent 的事件有 parent_session_id / parent_task_id。

## Phase 8：Web、Git、Batch、LSP、Patch 工具

### Web

先实现：

- `web_fetch`：抓取网页，转文本，长度限制，SSRF 拦截。
- `web_search`：默认不内置公网 API；先支持可配置 provider，未配置时返回明确错误。

Hermes 的 SSRF 防护应作为强制规则：

- 阻止 `127.0.0.0/8`
- 阻止 RFC1918 私网
- 阻止 `169.254.169.254`
- 阻止 `metadata.google.internal`

### Git

新增 `git` wrapper：

- 默认只允许 read-only git：`status/log/diff/show/branch`
- 写操作走 PermissionPolicy。
- destructive：`reset --hard`、`clean -fd`、`push --force` 默认 deny/ask。

### Batch

参考 OpenCode `batch.ts`：

- 允许并行执行 read-only 工具。
- 禁止 batch 自身、bash write、write/edit、MCP network 第一版进入 batch。
- 上限 10 或 25 个调用。

### LSP

参考 OpenCode `lsp.ts`：

- `go_to_definition`
- `find_references`
- `hover`
- `document_symbols`

第一版可不启动完整 LSP server，先接 `pyright`/`typescript-language-server` 后台能力或做接口预留。

### Patch / MultiEdit

Bamboo 已有 `edit/write`，但可以补：

- `apply_patch`：统一补丁格式，降低模型误改风险。
- `multi_edit`：单文件多处替换，必须全部匹配才提交。

## Phase 9：本地模型发现和向导

### Ollama

当前已支持 provider 调用。下一步补：

- 请求 `GET /api/tags` 发现本地模型。
- 若模型不存在，提示用户运行 `ollama pull <model>`。
- 可选自动 pull，但必须用户确认。
- 默认 base_url 统一为 `http://localhost:11434/v1`。

### vLLM

- 请求 `GET /v1/models` 发现模型。
- 支持 `VLLM_API_KEY`。
- base_url 默认 `http://localhost:8000/v1`。
- 启动时只做懒检测，避免无 vLLM 服务时报错。

### 文件

- 新增 `bamboo/llms/local_discovery.py`
- 增强 CLI 配置向导
- 增加 tests 使用 mock httpx transport

## 事件和可观测性

新增事件建议：

```text
tool-permission-request
tool-permission-result
tool-audit
todo-update
task-created
task-stopped
mcp-server-start
mcp-server-stop
mcp-tool-discovered
skill-scan
skill-install
command-run
subagent-start
subagent-finish
```

所有事件必须带：

- `session_id`
- `task_id`
- `tool_call_id` 如果适用
- `parent_session_id` 如果适用

## 优先级路线

### P0：立即做

1. ToolRegistry metadata/risk/block/source。
2. TodoWriteTool。
3. Task create/get/list/stop 基础版。
4. Bash command security + PermissionPolicy。
5. Tool audit log。

### P1：能力扩展

6. MCP stdio client + native tool registration。
7. SkillLoad 增强。
8. 移植开发类内置 skills。
9. Commands registry + command_run。

### P2：生态和智能化

10. SkillGuard + SkillHub。
11. Subagent runtime。
12. Web/Git/Batch tools。
13. Ollama/vLLM discovery。

### P3：高级开发体验

14. LSP tool。
15. ApplyPatch/MultiEdit。
16. Worktree 隔离子 Agent。
17. Plugin manifest/installer。

## 逐 Phase 文件改动清单

本节把每个 Phase 拆成明确的文件级改动。路径均相对仓库根目录 `/Users/liubaoyang/Documents/YoungL/agents/Bamboo`。

### Phase 0：ToolRegistry 元数据和权限基座

目标：先让工具注册表能表达来源、风险、禁用/阻塞状态，为后续 MCP、权限审批、插件工具做基础。

#### 修改现有文件

`bamboo/tools/buildin/base.py`

- 在 `Tool` 基类增加 class 属性：
  - `risk_level: str = "read"`
  - `tags: tuple[str, ...] = ()`
  - `is_builtin: bool = True`
- 在 `Tool.schema()` 输出中不直接暴露 `risk_level`，避免影响 LLM tool schema；风险信息只给 registry 和 PermissionPolicy 使用。
- `ToolResult.metadata` 保持可选，但约定所有工具可写入：
  - `duration_ms`
  - `truncated`
  - `risk_level`

`bamboo/tools/registry.py`

- 扩展 `ToolMetadata`：
  - `source: str`
  - `enabled: bool`
  - `blocked: bool`
  - `risk_level: str`
  - `tags: list[str]`
  - `registered_at: str`
- 修改 `register()`：
  - 从 `tool.risk_level` 填充 metadata。
  - 如果同名工具重复注册，记录旧 source 和新 source。
  - 默认允许后注册覆盖前注册，但保留测试覆盖。
- 修改 `get()`：
  - 如果工具不存在、disabled、blocked，返回 `None`。
- 新增方法：
  - `get_metadata(name: str) -> ToolMetadata | None`
  - `list_by_source(source_prefix: str) -> list[Tool]`
  - `block(name: str) -> bool`
  - `unblock(name: str) -> bool`
  - `register_mcp_tools(server: str, tools: list[Tool])`
  - `register_plugin_tools(plugin_name: str, tools: list[Tool])`
  - `set_mcp_client(server: str, client: Any)`
  - `get_mcp_client(server: str) -> Any | None`
- 修改 `summary()`：
  - 增加 `by_source`
  - 增加 `by_risk`
  - 增加 `blocked`

`bamboo/tools/buildin/__init__.py`

- 暂时不新增工具，只确保所有现有工具创建后有默认 `risk_level`。
- 给内置工具在 class 上标注风险：
  - `ReadTool/GlobTool/GrepTool/SkillLoadTool`: `read`
  - `WriteTool/EditTool`: `write`
  - `BashTool`: `execute`

`tests/test_tool_registry.py`

- 扩展现有测试：
  - 注册工具后 metadata 包含 source/risk_level。
  - disable 后 `get()` 返回 None。
  - block 后 `get()` 返回 None。
  - unblock 后恢复。
  - `list_by_source("mcp:")` 能筛选 MCP 工具。
  - `summary()` 输出 `by_source` 和 `by_risk`。

#### 新增文件

`bamboo/security/__init__.py`

- 新建 security 包入口。
- 第一阶段只导出空接口或基础类型，方便后续 Phase 3 引入 PermissionPolicy。

`tests/test_tool_metadata.py`

- 如果不想扩展 `test_tool_registry.py` 太大，可以单独放 metadata 测试。
- 覆盖内置工具的 `risk_level` 约定。

#### 不做的事

- 不在 Phase 0 引入审批流程。
- 不修改 `AgentRuntime._execute_tool_call()`。
- 不新增 MCP、todo、task 工具。

### Phase 1：Todo 和 Task 工具

目标：让模型能维护长任务计划，并能创建/查询任务快照。这个 Phase 是子 Agent 和 workflow 的前置基础。

#### 修改现有文件

`bamboo/tools/buildin/__init__.py`

- 导入并注册新增工具：
  - `TodoWriteTool`
  - `TaskCreateTool`
  - `TaskGetTool`
  - `TaskListTool`
  - `TaskStopTool`
- `create_builtin_tools()` 返回列表中加入这些工具。
- `__all__` 增加对应类名。

`bamboo/runtime/store.py`

- 扩展 `TaskSnapshot`：
  - `title: str = ""`
  - `created_at: str = ""`
  - `updated_at: str = ""`
  - `metadata: dict[str, str] = field(default_factory=dict)`
- `save_created()`：
  - 保存 title，初期用 `task.user_query[:80]`。
  - 写入 created_at/updated_at。
- `save_status()` 和 `save_error()`：
  - 更新 `updated_at`。
- 新增方法：
  - `list(self, *, session_id: str | None = None) -> list[TaskSnapshot]`
  - `stop(self, task_id: str, reason: str = "") -> TaskSnapshot | None`
  - `save_metadata(self, task_id: str, metadata: dict[str, str]) -> None`

`bamboo/runtime/task_runtime.py`

- 在 `_transition_task()` 中，如果 to_status 是 `cancelled`，允许 `running -> cancelled`。
- 失败/完成前检查 task 是否被 stop 标记，第一版可以只在状态层体现，不强行中断正在运行的 agent。

`bamboo/helpers/constant.py`

- 新增事件 dataclass：
  - `TodoUpdateEvent`
  - `TaskStopEvent`
  - `TaskSnapshotEvent`
- 或者如果现有事件文件结构不适合，先新增事件类型常量并保持 BaseEvent 风格一致。

`bamboo/runtime/agent_runtime.py`

- `_execute_tool_call()` 对 `todo_write`、`task_*` 不需要特殊分支，仍走普通工具。
- 但工具执行结果事件 `ToolResultEvent` 应包含 metadata 时可以透传，便于 UI 后续展示 todo/task 状态。

#### 新增文件

`bamboo/tools/buildin/todo.py`

- 定义 `TodoItem` dataclass：
  - `id: str`
  - `content: str`
  - `status: Literal["pending", "in_progress", "completed"]`
- 定义 `TodoWriteTool`：
  - `name = "todo_write"`
  - `risk_level = "write"`
  - input schema：`todos: list[TodoItem]`
- `execute()`：
  - 校验同一时间最多一个 `in_progress`。
  - 输出简短摘要，例如 `3 todos, 1 in progress, 1 completed`。
  - `metadata={"todos": todos}`。
- 第一版不持久化到磁盘，由调用方从 metadata 写入 session/task 后续实现。

`bamboo/tools/buildin/task.py`

- 定义四个工具：
  - `TaskCreateTool`
  - `TaskGetTool`
  - `TaskListTool`
  - `TaskStopTool`
- 工具内部通过 `get_task_store()` 或注入 store 获取状态。
- 如果当前项目还没有全局 task store，先在 `bamboo/runtime/store.py` 增加 `get_task_store()` 单例。
- `task_create` 输入：
  - `title`
  - `description`
  - `tags`
  - `depends_on`
- `task_get` 输入：
  - `task_id`
- `task_list` 输入：
  - `session_id`
  - `status`
- `task_stop` 输入：
  - `task_id`
  - `reason`

`tests/test_todo_tool.py`

- 覆盖：
  - schema required。
  - 正常更新 todo。
  - 多个 in_progress 返回失败。
  - metadata 中保留 todos。

`tests/test_task_tools.py`

- 覆盖：
  - create 后 get 可查。
  - list 按 session 过滤。
  - stop 后状态为 cancelled。
  - 不存在 task_id 返回失败。

#### 不做的事

- 不做真正异步后台 worker。
- 不做 task cancellation 的 asyncio task cancel。
- 不做 Web UI todo 展示。

### Phase 2：MCP 接入

目标：支持 stdio MCP server，启动时发现 MCP tools，并注册成 Bamboo 原生工具。

#### 修改现有文件

`bamboo/tools/registry.py`

- 使用 Phase 0 已新增的 MCP client 管理方法。
- `register_mcp_tools()` 将 source 设置为 `mcp:<server>`。
- MCP 工具默认 `risk_level = "network"`，允许 server 配置覆盖。

`bamboo/runtime/runtime_context.py`

- 在 `RuntimeContextBuilder.build(task)` 中加载 MCP：
  - 读取配置。
  - 启动 MCP manager。
  - 将发现到的 MCP tool 注册进 `tool_registry`。
- 将 MCP manager 保存到 `RuntimeContext`，方便 task 结束时关闭或复用。

`bamboo/runtime/task_runtime.py`

- 在 task 完成或失败时，调用 runtime context 的 cleanup hook。
- 第一版可以保持 MCP server 进程级复用，不每个 task 都重启；但必须有显式 shutdown 方法。

`bamboo/helpers/config.py`

- 增加读取 `mcp.yaml` 的 helper，或让 BambooConfig 支持 `mcp` namespace。
- 用户配置优先级：
  - project `.bamboo/mcp.yaml`
  - `~/.bamboo/configs/mcp.yaml`
  - package `bamboo/configs/mcp.yaml`

`bamboo/helpers/redact.py`

- 扩展 token redaction patterns：
  - GitHub PAT
  - OpenAI key
  - Bearer token
  - `token=`
  - `password=`
  - `secret=`
  - `api_key=`

#### 新增文件

`bamboo/configs/mcp.yaml`

- 包内默认配置：

```yaml
mcp:
  auto_start: false
  servers: {}
```

`bamboo/tools/mcp/__init__.py`

- MCP 包入口。
- 导出 `MCPClient`、`MCPManager`、`MCPProxyTool`、`MCPDiscoveredTool`。

`bamboo/tools/mcp/models.py`

- dataclass：
  - `MCPServerConfig`
  - `MCPToolDefinition`
  - `MCPCallResult`

`bamboo/tools/mcp/client.py`

- 实现 stdio JSON-RPC client：
  - `start()`
  - `initialize()`
  - `list_tools()`
  - `call_tool(name, arguments)`
  - `stop()`
- 处理：
  - request id。
  - stdout readline。
  - stderr 收集上限。
  - timeout。
  - server exit。

`bamboo/tools/mcp/manager.py`

- 管理多个 MCP client：
  - `load_from_config(config)`
  - `start_all()`
  - `discover_tools()`
  - `stop_all()`
- 环境变量过滤：
  - 默认只传 `PATH/HOME/USER/LANG/LC_ALL/TERM/SHELL/TMPDIR`。
  - 配置 env 中显式声明的变量才传入。

`bamboo/tools/mcp/tool.py`

- `MCPProxyTool`：
  - `name = "mcp"`
  - 输入 `server/tool/arguments`
  - 作为 fallback。
- `MCPDiscoveredTool`：
  - 每个 MCP remote tool 包一层 Bamboo Tool。
  - name 格式：`mcp_{server}_{tool}`。
  - input_schema 直接来自 MCP `inputSchema`。
  - execute 调用对应 client。

`tests/test_mcp_client.py`

- 使用 fake stdio process 或 mock stream。
- 覆盖 initialize、tools/list、tools/call。

`tests/test_mcp_tools.py`

- 覆盖 `MCPDiscoveredTool.schema()`。
- 覆盖 manager 注册工具到 ToolRegistry。
- 覆盖错误脱敏。

#### 不做的事

- 第一版不做 HTTP/StreamableHTTP MCP。
- 第一版不做 OAuth MCP。
- 第一版不做自动重连；只要求失败可见、进程可关闭。

### Phase 3：Bash 安全、权限审批和审计

目标：所有工具调用前经过 PermissionPolicy，bash 命令有风险分类，工具执行有结构化审计。

#### 修改现有文件

`bamboo/runtime/agent_runtime.py`

- 修改 `_execute_tool_call()`：
  1. 根据 tool_name 从 registry 获取 tool。
  2. 构造 `PermissionRequest`。
  3. 调用 `PermissionPolicy.evaluate()`。
  4. 如果 deny：写入 tool error，发 PermissionResultEvent。
  5. 如果 ask：发 PermissionRequestEvent，等待 adapter 返回决定。
  6. allow 后执行工具。
  7. 执行结束写入 audit log。
- 保持原有 `ToolCallEvent/ToolResultEvent/ToolErrorEvent` 不破坏。

`bamboo/tools/buildin/bash.py`

- 在 execute 前调用 `classify_command()`。
- 将分类写入 `ToolResult.metadata`。
- 接收 `permission_context` 可选参数；如果没有，仍由 AgentRuntime 前置审批。
- 对危险命令返回失败，不直接执行。

`bamboo/tools/buildin/write.py`

- 标注 `risk_level = "write"`。
- metadata 中记录 path。

`bamboo/tools/buildin/edit.py`

- 标注 `risk_level = "write"`。
- metadata 中记录 path、old/new 是否匹配。

`bamboo/helpers/constant.py`

- 新增事件：
  - `PermissionRequestEvent`
  - `PermissionResultEvent`
  - `ToolAuditEvent`

`bamboo/adapters/cli/main.py`

- 订阅 permission 事件。
- 当 `PermissionRequestEvent` 到达：
  - 如果 `run_params.yes_all` 且策略允许 auto approve，则返回 allow。
  - 否则在终端询问用户。
- 第一版可以通过 EventBus callback 或 runtime-provided resolver 实现；如果现有 EventBus 不支持 request/response，需要加一个简单 `PermissionResolver` 注入 RuntimeContext。

`bamboo/adapters/web/app.py`

- 第一版可以对 ask 返回 error，提示 Web 暂不支持交互审批。
- 后续通过 stream event 让前端确认。

#### 新增文件

`bamboo/security/command_security.py`

- `CommandCategory` enum：
  - `READ_ONLY`
  - `WRITE`
  - `DESTRUCTIVE`
  - `NETWORK`
  - `UNKNOWN`
- `SecurityCheckResult` dataclass。
- regex lists：
  - `DANGEROUS_PATTERNS`
  - `CONFIRM_PATTERNS`
  - `READ_ONLY_KEYWORDS`
  - `WRITE_KEYWORDS`
  - `NETWORK_KEYWORDS`
- functions：
  - `classify_command(command: str) -> CommandCategory`
  - `check_dangerous(command: str) -> bool`
  - `check_requires_confirmation(command: str) -> bool`
  - `security_check(command: str) -> SecurityCheckResult`

`bamboo/security/permission_policy.py`

- `PermissionDecision` enum。
- `PermissionMode` enum。
- `PermissionRequest` dataclass。
- `PermissionResult` dataclass。
- `PermissionPolicy` class：
  - `evaluate(request, run_params) -> PermissionResult`
  - `evaluate_tool_risk(tool_name, metadata, arguments)`
  - `evaluate_bash(command)`
- 默认规则：
  - read allow。
  - write ask。
  - execute ask。
  - network ask。
  - destructive deny。

`bamboo/security/audit_log.py`

- `ToolAuditRecord` dataclass。
- `ToolAuditLogger`：
  - `append(record)`
  - 写入 `~/.bamboo/storage/audit/tools.jsonl`。
- 写入前调用 redaction。

`bamboo/security/sandbox.py`

- 先放配置和接口，不强制接入：
  - `SandboxConfig`
  - `SandboxResult`
  - `run_sandboxed(command, config)`
- 可从 Auton 方案简化。

`tests/test_command_security.py`

- 覆盖：
  - `ls`, `git status` -> read。
  - `touch`, `mkdir`, redirect -> write。
  - `rm -rf /`, `curl | sh`, `git reset --hard` -> destructive。

`tests/test_permission_policy.py`

- 覆盖不同 mode 下 read/write/execute/destructive。
- 覆盖 `yes_all` 不允许绕过 destructive。

`tests/test_tool_audit.py`

- 使用 tmp dir 写 audit jsonl。
- 验证 token redaction。

#### 不做的事

- 不在 Phase 3 强制启用 OS sandbox。
- 不做 Web UI 交互审批完整闭环。

### Phase 4：SkillLoad 增强和内置 Skill 库

目标：把 skill 从“能加载”升级为“模型容易发现、加载后容易继续读资源”，并补内置开发工作流 skills。

#### 修改现有文件

`bamboo/tools/buildin/skill_load.py`

- 修改 `description` 生成方式：
  - 初始化时如果有 registry，动态列出 skill catalog。
  - 无 registry 时，execute 时再构建可用列表。
- `execute()` 输出改为结构化块：
  - `<skill_content name="...">`
  - `# Skill: ...`
  - SKILL.md 内容
  - `<skill_base_dir>...</skill_base_dir>`
  - `<skill_files>...</skill_files>`
- 如果 skill 不存在：
  - 返回失败。
  - content 中列出 available skills。

`bamboo/skills/registry.py`

- 新增方法：
  - `render_tool_catalog(verbose: bool = False) -> str`
  - `list_resource_files(name: str, limit: int = 20) -> list[str]`
- 修改 `load_skill_content()`：
  - 可选包含 base dir 和 sampled files。
  - 或保持原方法纯内容，结构化输出由 `SkillLoadTool` 负责。

`bamboo/skills/creator.py`

- 如果生成 skill 模板，补充 `metadata.bamboo.tags` 示例。

`bamboo/skills/validator.py`

- 增加可选校验：
  - name <= 64。
  - description <= 1024。
  - metadata.bamboo.tags 如果存在必须是 list[str]。

`tests/test_skills.py`

- 增加：
  - `render_tool_catalog()` 测试。
  - `list_resource_files()` 测试。
  - `skill_load` 输出包含 base dir。

#### 新增文件和目录

`bamboo/skills/buildin/systematic-debugging/SKILL.md`

- 从 Hermes `systematic-debugging` 改写。
- 替换工具名：
  - `read_file` -> `read`
  - `search_files` -> `grep`
  - `terminal` -> `bash`
- 删除 Hermes 专属说明。

`bamboo/skills/buildin/test-driven-development/SKILL.md`

- 从 Hermes `test-driven-development` 改写。
- 强调 Bamboo 工作流：
  - 先写测试。
  - 运行特定测试。
  - 再实现。
  - 最后跑相关全量测试。

`bamboo/skills/buildin/writing-plans/SKILL.md`

- 迁移 Hermes planning skill 或根据 Bamboo 文档风格新写。
- 用于复杂改动前写实施计划。

`bamboo/skills/buildin/requesting-code-review/SKILL.md`

- 迁移 Hermes code review skill。
- 输出按 findings-first。

`bamboo/skills/buildin/github-pr-workflow/SKILL.md`

- 迁移 Hermes GitHub PR workflow。
- 保留 gh CLI 优先、curl fallback。
- 注意安全：token 不输出。

`bamboo/skills/buildin/native-mcp/SKILL.md`

- 不是实现 MCP，而是写 Bamboo MCP 配置/排障说明。
- 在 Phase 2 完成后启用。

`tests/fixtures/skills/skill-with-resources/`

- 放测试用 SKILL.md、references、scripts。

#### 不做的事

- 不做 SkillHub 下载。
- 不做外部 skill 安全扫描。

### Phase 5：Skill Hub 和 Skill Guard

目标：允许安装外部 skill，但必须 quarantine、scan、lockfile。

#### 修改现有文件

`bamboo/skills/store.py`

- 增加 hub 目录 helper：
  - `hub_dir()`
  - `quarantine_dir()`
  - `lock_path()`
  - `audit_path()`
- 增加 lockfile 读写：
  - `load_hub_lock()`
  - `save_hub_lock()`
  - `append_hub_audit()`

`bamboo/skills/models.py`

- 新增 dataclass：
  - `SkillHubSource`
  - `SkillHubLockEntry`
  - `SkillScanFinding`
  - `SkillScanResult`
- `SkillDefinition` 可选增加：
  - `trust_level: str = "local"`
  - `origin: str = ""`

`bamboo/skills/registry.py`

- refresh 时读取 lockfile，为来自 hub 的 skill 填 origin/trust_level。
- 如果 scan state 是 blocked，不进入 active list。

`bamboo/adapters/cli/main.py`

- 如果 CLI 结构适合，增加子命令入口：
  - `bamboo skills list`
  - `bamboo skills install`
  - `bamboo skills scan`
- 如果当前 CLI 还不支持子命令，先新增独立 module，暂不挂入口。

#### 新增文件

`bamboo/skills/guard.py`

- 从 Hermes `skills_guard.py` 精简迁移。
- 定义：
  - `Finding`
  - `ScanResult`
  - `scan_skill(path: Path, source: str) -> ScanResult`
  - `should_allow_install(result, trust_level) -> tuple[bool, str]`
  - `format_scan_report(result) -> str`
- threat patterns：
  - exfiltration
  - prompt injection
  - destructive
  - persistence
  - network tunnel
  - obfuscation

`bamboo/skills/hub.py`

- 第一版只支持 GitHub source。
- 定义：
  - `SkillSource` ABC
  - `GitHubSkillSource`
  - `SkillBundle`
  - `SkillHub`
- `SkillHub.install(identifier)` 流程：
  1. 下载到 quarantine。
  2. 校验路径。
  3. scan。
  4. policy allow 后移动到 `~/.bamboo/skills/<name>`。
  5. 写 lockfile 和 audit。

`bamboo/skills/cli.py`

- CLI helper：
  - `list_skills()`
  - `install_skill(identifier, force=False)`
  - `scan_skill_path(path)`
- 未来挂到主 CLI。

`tests/test_skill_guard.py`

- safe skill。
- prompt injection skill。
- secret exfil skill。
- destructive command skill。

`tests/test_skill_hub.py`

- 使用本地 fake source，不访问网络。
- 验证 quarantine -> active。
- 验证 lockfile。
- 验证 dangerous 被 block。

#### 不做的事

- 不做 ClawHub/agentskills.io 搜索。
- 不做 GitHub API 网络测试。
- 不做自动更新。

### Phase 6：Commands 系统

目标：引入轻量命令模板，适合 commit、changelog、learn、issues 这类流程。

#### 修改现有文件

`bamboo/commands/__init__.py`

- 从空文件改为导出：
  - `CommandDefinition`
  - `CommandRegistry`
  - `create_command_registry`

`bamboo/tools/buildin/__init__.py`

- 注册 `CommandRunTool`。

`bamboo/runtime/prompt.py`

- 如果 prompt builder 有 tools catalog section，可把可用 commands 摘要作为独立 section。
- 第一版也可只通过 `command_run` 工具 description 动态列出。

`bamboo/helpers/config.py`

- 增加 commands 搜索路径 helper：
  - package built-in
  - user
  - project

#### 新增文件和目录

`bamboo/commands/models.py`

- `CommandDefinition`：
  - `name`
  - `description`
  - `source_path`
  - `source`
  - `model`
  - `subtask`
  - `body`

`bamboo/commands/registry.py`

- 扫描：
  - `bamboo/commands/buildin/*.md`
  - `~/.bamboo/commands/*.md`
  - `<project>/.bamboo/commands/*.md`
- 解析 YAML frontmatter。
- 支持 `$ARGUMENTS` 替换。
- project 覆盖 user，user 覆盖 builtin。

`bamboo/tools/buildin/command_run.py`

- `CommandRunTool`：
  - `name = "command_run"`
  - 输入 `name`、`arguments`
  - 输出展开后的 prompt。
- 第一版只返回内容给模型，不自动递归调用 Agent。
- 后续可将展开 prompt 追加到 session 并继续 run。

`bamboo/commands/buildin/commit.md`

- 参考 OpenCode `.opencode/command/commit.md`，改成 Bamboo 风格。

`bamboo/commands/buildin/changelog.md`

- 生成 changelog 的流程命令。

`bamboo/commands/buildin/learn.md`

- 把本轮非显然经验写入 AGENTS.md/BAMBOO.md 的流程命令。

`bamboo/commands/buildin/rmslop.md`

- 清理 AI 代码痕迹的流程命令。

`tests/test_command_registry.py`

- frontmatter 解析。
- `$ARGUMENTS` 替换。
- project override。

`tests/test_command_run_tool.py`

- command 存在时返回展开 prompt。
- 不存在时列出 available commands。

#### 不做的事

- 第一版不支持 `!` shell interpolation。
- 第一版不按 command model 切换模型，只记录 metadata。

### Phase 7：Subagent Runtime

目标：把 Bamboo 空的 subagents 目录落地，支持只读/受限子 Agent。

#### 修改现有文件

`bamboo/runtime/runtime_context.py`

- `RuntimeContext` 增加：
  - `subagent_registry`
  - `parent_session_id`
  - `parent_task_id`
- `RuntimeContextBuilder` 支持根据 agent profile 构建受限 ToolRegistry。

`bamboo/runtime/task_runtime.py`

- 增加 `run_subtask(parent_task, subagent_name, prompt)` helper。
- 子任务使用同一个 EventBus，但事件带 parent 信息。

`bamboo/factory/session.py`

- Session 支持 `parent_session_id`。
- 如果当前 Session dataclass 没字段，先放 metadata。

`bamboo/factory/task_factory.py`

- `Task` 增加 `parent_task_id: str = ""` 或 metadata 记录。

`bamboo/tools/buildin/__init__.py`

- 如果 Phase 1 的 `task.py` 已存在，在里面追加 `TaskDelegateTool`。
- 或新增 `subagent_task` 工具。

#### 新增文件

`bamboo/subagents/__init__.py`

- 导出 subagent models/registry。

`bamboo/subagents/models.py`

- `SubagentDefinition`：
  - `name`
  - `description`
  - `model`
  - `tools`
  - `permission`
  - `source_path`

`bamboo/subagents/registry.py`

- 扫描：
  - `bamboo/subagents/buildin/*.yaml`
  - `~/.bamboo/agents/*.yaml`
  - `<project>/.bamboo/agents/*.yaml`
- 校验工具 allow/deny。

`bamboo/runtime/subagent_runtime.py`

- `SubagentRuntime`：
  - 创建子 session。
  - 根据 SubagentDefinition 创建受限 RuntimeContext。
  - 调用 AgentRuntime。
  - 返回 `<task_result>`。

`bamboo/tools/buildin/subagent_task.py`

- `TaskDelegateTool`：
  - `name = "task"`
  - 输入 `description/prompt/subagent_type/task_id`
  - 输出 task_id + task_result。

`bamboo/subagents/buildin/explorer.yaml`

- 只读探索 agent。

`bamboo/subagents/buildin/planner.yaml`

- 只读规划 agent。

`bamboo/subagents/buildin/verifier.yaml`

- 允许 read/grep/glob/bash read-only。

`bamboo/subagents/buildin/reviewer.yaml`

- 只读审查 agent。

`tests/test_subagent_registry.py`

- 扫描和 override。
- 工具 allow/deny 解析。

`tests/test_subagent_runtime.py`

- 使用 stub LLM client。
- 验证子 Agent 工具被收窄。
- 验证 parent_session_id。

#### 不做的事

- 第一版不允许子 Agent 写文件。
- 第一版不做 worktree。
- 第一版不做多进程。

### Phase 8：Web、Git、Batch、LSP、Patch 工具

目标：补齐高频 coding agent 工具，但每个工具都要经过 PermissionPolicy。

#### 修改现有文件

`bamboo/tools/buildin/__init__.py`

- 注册：
  - `WebFetchTool`
  - `WebSearchTool`
  - `GitTool`
  - `BatchTool`
  - `ApplyPatchTool`
  - `MultiEditTool`
  - `LSPTool` 可选

`bamboo/tools/buildin/file_filter.py`

- 复用到 web/git/batch 输出过滤。
- 增加 binary 文件检测 helper 可选。

`bamboo/security/permission_policy.py`

- 增加 web/git/batch/lsp 的 risk 规则。
- Git destructive 子命令特殊处理。
- Batch 中每个子工具仍需要评估 permission。

`bamboo/security/command_security.py`

- 增加 `classify_git_args(args: str)`。

#### 新增文件

`bamboo/tools/buildin/web_fetch.py`

- 输入：
  - `url`
  - `max_length`
- 使用 `httpx`。
- 先做 URL 安全检查：
  - 禁止 localhost/private/link-local/cloud metadata。
  - 禁止非 http/https。
- HTML 转文本第一版可用简单 parser，后续再引入 readability。

`bamboo/tools/buildin/web_search.py`

- 输入：
  - `query`
  - `limit`
- 第一版如果没有配置 provider，返回明确错误。
- 后续接 Brave/SerpAPI/Tavily。

`bamboo/security/url_safety.py`

- `is_url_allowed(url) -> tuple[bool, str]`
- DNS 解析后检查 IP 网段。
- 保护云 metadata。

`bamboo/tools/buildin/git.py`

- 输入：
  - `args`
  - `cwd`
- 内部调用 BashTool 或 subprocess。
- read-only git 直接 allow，写操作走 PermissionPolicy。

`bamboo/tools/buildin/batch.py`

- 输入：
  - `tool_calls: list[{tool, arguments}]`
- 限制：
  - 最多 10 或 25 个。
  - 禁止 batch 调 batch。
  - 第一版只允许 read risk 工具。

`bamboo/tools/buildin/apply_patch.py`

- 输入：
  - `patch`
- 解析统一 patch 格式。
- 必须只写 workspace 内文件。
- 可复用现有 `edit/write` 逻辑。

`bamboo/tools/buildin/multi_edit.py`

- 输入：
  - `path`
  - `edits: list[{old, new}]`
- 所有 old 必须唯一匹配，否则整个操作失败。
- 写入前可生成 preview metadata。

`bamboo/tools/buildin/lsp.py`

- 输入：
  - `operation`
  - `file_path`
  - `line`
  - `character`
- 第一版可返回 `No LSP server configured`，先把接口稳定下来。
- 后续接 pyright/typescript-language-server。

`tests/test_url_safety.py`

- 禁止 private IP、metadata。
- 允许公网 URL。

`tests/test_git_tool.py`

- git status/log/diff。
- git reset --hard 触发 destructive。

`tests/test_batch_tool.py`

- 只读工具 batch 成功。
- write/bash destructive 被拒。

`tests/test_multi_edit_tool.py`

- 多处替换全部成功。
- 任一 old 不匹配则不写文件。

#### 不做的事

- 不在第一版引入真实 web_search provider。
- LSP 第一版可以只做接口和错误提示。

### Phase 9：Ollama/vLLM 本地模型发现和向导

目标：在已有 provider 调用层上补本地模型 discovery 和配置体验。

#### 修改现有文件

`bamboo/llms/providers/ollama.py`

- 增加可选 discovery helper 或保持 provider 纯调用。
- 推荐不要把 discovery 混进 client，放到 `local_discovery.py`。

`bamboo/llms/providers/vllm.py`

- 同上，保持调用层轻量。

`bamboo/llms/factory.py`

- 不在 get_client 时做 discovery，避免服务未启动导致 Bamboo 启动失败。
- 可增加显式方法：
  - `discover_local_models(provider: str)`

`bamboo/configs/models.yaml`

- 保留 `ollama-local`、`vllm-local` 示例。
- 注释说明可以使用 discovery 命令生成配置。

`bamboo/adapters/cli/main.py`

- 后续增加配置向导命令：
  - `bamboo models discover ollama`
  - `bamboo models discover vllm`
- 如果 CLI 结构暂不支持子命令，先新增模块不挂入口。

#### 新增文件

`bamboo/llms/local_discovery.py`

- `LocalModelInfo` dataclass：
  - `provider`
  - `model`
  - `base_url`
  - `context_window`
- `OllamaDiscovery`：
  - `list_models(base_url="http://localhost:11434")`
  - 调 `/api/tags`
  - 转换为 Bamboo model config 建议。
- `VLLMDiscovery`：
  - `list_models(base_url="http://localhost:8000/v1")`
  - 调 `/models`
  - 支持 api_key。
- 所有网络失败都返回结构化错误，不抛到启动链路。

`bamboo/llms/model_config_writer.py`

- 可选。
- 把 discovery 结果写入用户 `~/.bamboo/configs/models.yaml`。
- 必须先备份。

`bamboo/adapters/cli/models.py`

- CLI helper：
  - `discover_ollama()`
  - `discover_vllm()`
  - `print_model_config_snippet()`

`tests/test_local_model_discovery.py`

- 使用 `httpx.MockTransport`。
- 覆盖 Ollama `/api/tags`。
- 覆盖 vLLM `/v1/models`。
- 覆盖连接失败。

#### 不做的事

- 不在用户未确认时自动 `ollama pull`。
- 不在启动时自动探测本地服务。
- 不修改默认模型。

## 测试策略

每个阶段至少补三类测试：

1. Unit test：工具 schema、参数校验、执行结果。
2. Runtime test：AgentRuntime 调用工具后的 session message/event。
3. Security test：危险输入不能绕过 PermissionPolicy。

关键测试文件建议：

```text
tests/test_tool_registry.py
tests/test_todo_tool.py
tests/test_task_tools.py
tests/test_permission_policy.py
tests/test_command_security.py
tests/test_mcp_tools.py
tests/test_skill_guard.py
tests/test_command_registry.py
tests/test_subagent_runtime.py
```

## 兼容性和迁移

- 保持现有工具名可用，不强制改用户 prompt。
- 新工具只增加，不替换现有 `bash/read/write/edit`。
- `RunParams.permission` 继续兼容，内部映射到 PermissionPolicy mode。
- `SkillRegistry` 现有 state/index/usage 文件格式尽量不破坏；新增字段必须可选。
- MCP、SkillHub、Commands 默认关闭或空配置，不影响现有启动。

## 风险

### MCP 安全风险

MCP server 是外部进程，不能默认继承全部 env。必须先做 env allowlist 和错误脱敏。

### PermissionPolicy 体验风险

审批太频繁会拖慢 agent。需要按 risk_level 和 permission mode 做合理默认值。

### SkillHub 供应链风险

外部 skill 是 prompt + 脚本混合体，必须 quarantine + scan + lockfile。不要先做一键安装再补扫描。

### Subagent 写入冲突

第一版子 Agent 禁写或只允许只读。并行写入必须等 worktree 隔离后再开放。

## 建议第一批 PR 拆分

1. `tool-registry-metadata`：ToolMetadata 扩展、risk_level、block/source。
2. `todo-tool`：TodoWriteTool + TodoUpdateEvent。
3. `task-tools`：TaskStore 扩展 + task_create/get/list/stop。
4. `permission-policy`：command_security、PermissionPolicy、audit log。
5. `mcp-stdio`：MCP client + native registration。
6. `skill-load-upgrade`：动态 skill catalog + base dir + sampled files。
7. `builtin-dev-skills`：迁移 systematic-debugging/TDD/writing-plans。

这个拆法能保证每一步都可独立测试、独立回滚。
