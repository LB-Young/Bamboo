# Bamboo Agent 剩余 Todo

本目录只保留当前还没有完成的开发项。已经完成的能力不再保留 todo，避免后续重复实现。

## 已完成并移除的条目

- RuntimeContextBuilder：已由 `bamboo/runtime/runtime_context.py` 实现。
- Prompt Section Pipeline：已由 `bamboo/prompts/system_prompt.py` 和 `bamboo/runtime/prompt.py` 实现基础分段。
- Permission Policy：已由 `bamboo/security/permission_policy.py`、resolver、audit 和 AgentRuntime 接入实现。
- Skills Hub / Guard：已由 `bamboo/skills/hub.py`、`guard.py`、CLI 和 lock/audit 实现。
- Subagent Runtime：已由 `bamboo/runtime/subagent_runtime.py`、`bamboo/tools/buildin/subagent_run.py` 和内置 subagent 配置实现。
- Model Fallback And Auxiliary Router：已由 `bamboo/llms/router.py`、结构化 LLM 错误和 AgentRuntime fallback 接入实现。
- Reactive Compact：已由 `ContextCompactor.compact(force=True)`、`SessionCompactEvent.reason` 和 AgentRuntime reactive retry 实现。
- Provider Specific Prompt：已由 `ModelConfig.prompt_profile/capabilities`、provider prompt section 和 PromptBuilder 接入实现。
- Agent Trace Events：已由 `parent_event_id`、EventBus pattern 订阅、LLM 脱敏事件和 TraceRecorder 实现基础链路。
- Workflow Runner：已改为 skill-like workflow 文档包，通过 `workflow_load` / `workflow_run` 工具读取说明并执行声明脚本。
- Cron And Heartbeat：已由 `bamboo/cron`、`bamboo cron`、`~/.bamboo/cron/jobs.yaml`、retry 和 jsonl 执行日志实现。
- OS Sandbox Runner：已由 `bamboo/security/sandbox.py`、`BashTool` sandbox 接入和 audit sandbox 元数据实现。
- Readonly Tool Parallelism：已由 `AgentRuntime` 同轮 read-only tool calls 并发执行和稳定顺序写回实现。

## 排期原则

- 优先补齐安全和生命周期闭环：Web 权限审批、MCP 进程清理、trace schema 先做，否则后续能力难以稳定接入 UI、回放和审计。
- 其次补齐用户高频能力：记忆更新、本地模型发现、cron 主会话投递。
- 最后做高级扩展：评估工具、辅助模型细分、subagent worktree、plugin installer。
- `P2-05 Session Resume And Replay` 的需求 md 已不存在，代码中已有 `--resume` / `replay` 相关实现入口；后续 replay 能力统一并入 `P2-10 Evaluation And Replay Tools` 扩展，不再单独排期。

## 当前剩余条目

| 建议顺序 | 需求 | 功能说明 | 重要程度 | 优先级 | 依赖/备注 |
| --- | --- | --- | --- | --- | --- |
| 1 | `P2-13-web-permission-approval-flow.md` | Web 端补齐权限审批闭环：收到 `write/network/unknown` 工具请求后弹窗，用户批准或拒绝再回传运行时继续执行。 | 极高 | P0 | 直接影响 Web 模式可用性和安全边界。 |
| 2 | `P2-15-mcp-lifecycle-cleanup.md` | 明确 MCP server 生命周期，确保任务完成、异常、取消时不会遗留 MCP 子进程，并能记录启动/停止错误。 | 极高 | P0 | 涉及外部进程泄漏和资源清理，应在继续扩展 MCP 前完成。 |
| 3 | `P2-09-agent-trace-schema-docs.md` | 固化 EventBus/TraceRecorder 对外事件 schema，补文档和 schema 测试，让 Web、replay、外部工具能稳定消费事件。 | 高 | P0 | 是 replay/eval、Web 调试、cron 投递可观测性的基础。 |
| 4 | `P2-04-prompt-section-object-model.md` | 把 prompt 从字符串拼接升级为显式 `PromptSection` 对象，记录 section 来源、优先级、hash 和 debug 元数据。 | 高 | P1 | 有助于调试 provider prompt、memory、skills 注入；不阻塞安全闭环。 |
| 5 | `P2-06-memory-update-and-backfill-tools.md` | 新增 memory read/search/update/backfill 工具，让用户能通过对话修正知识，并把 source log 中的高价值信息回填到 knowledge md。 | 高 | P1 | 建议在 PromptSection 之后做，方便验证 memory 更新后 prompt 注入是否生效。 |
| 6 | `P2-11-local-model-discovery.md` | 增加 Ollama `/api/tags`、vLLM `/v1/models` 发现能力，输出或可选写入 `models.yaml` 配置片段。 | 高 | P1 | 用户可见收益大，且与主运行时耦合低，适合独立交付。 |
| 7 | `P2-08-cron-main-session-delivery.md` | 让 cron job 支持 `isolated` 和真实 `main` 投递，把定时任务结果追加到指定活跃会话并推送 Web/CLI。 | 中高 | P1 | 依赖 trace/schema 和 session 查找能力；否则 UI 侧难以稳定消费。 |
| 8 | `P2-10-evaluation-and-replay-tools.md` | 建立 eval/replay 工具链，用 session trace 或 fixture 复现失败、比较模型/prompt/tool 行为变化并输出报告。 | 中高 | P2 | 建议在 trace schema 固化后做；可复用已有 `replay` 初版。 |
| 9 | `P2-07-auxiliary-model-router-expansion.md` | 把 auxiliary router 从 compaction 扩展到 memory、skills_hub、web_extract、vision 等角色，并支持各自 fallback。 | 中 | P2 | 当前 compaction 已够用；等 memory/skills 等真实调用点更多后再扩展更稳。 |
| 10 | `P2-16-subagent-worktree-isolation.md` | 给可写 subagent 增加 worktree/tempdir 隔离，子 Agent 完成后返回 diff/summary，避免污染主工作区。 | 中 | P2 | 对多 Agent 并行写代码很重要，但实现复杂，建议排在安全基础之后。 |
| 11 | `P2-17-plugin-manifest-installer.md` | 定义 Bamboo plugin manifest 和安装/卸载链路，组合发布 skills、commands、workflows、MCP 配置片段。 | 中低 | P3 | 属于分发和生态能力，等核心运行时与安全模型稳定后再做。 |

## 建议阶段

### P0：安全闭环和运行时基础

1. `P2-13-web-permission-approval-flow.md`
2. `P2-15-mcp-lifecycle-cleanup.md`
3. `P2-09-agent-trace-schema-docs.md`

### P1：核心用户能力

1. `P2-04-prompt-section-object-model.md`
2. `P2-06-memory-update-and-backfill-tools.md`
3. `P2-11-local-model-discovery.md`
4. `P2-08-cron-main-session-delivery.md`

### P2：质量工程和高级运行时

1. `P2-10-evaluation-and-replay-tools.md`
2. `P2-07-auxiliary-model-router-expansion.md`
3. `P2-16-subagent-worktree-isolation.md`

### P3：生态和分发

1. `P2-17-plugin-manifest-installer.md`

## 实施原则

- 每次只做一个需求，避免跨模块大面积重构。
- 已有能力优先复用：工具走 `ToolRegistry`，审批走 `PermissionPolicy`，委派走 `SubagentRuntime`，可复用流程走 `Command` 或 `Skill`。
- 新运行时能力继续接入主链路：`TaskFactory -> TaskRuntime -> AgentRuntime -> EventBus`。
- 用户空间内容优先可配置，包内内容只作为默认模板。
