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

## 当前剩余条目

- `P2-04-prompt-section-object-model.md`：把当前 prompt 字符串拼接升级为显式 `PromptSection` 对象和 hash/debug 元数据。
- `P2-05-session-resume-and-replay.md`：实现 `--resume` 和 `replay`，从持久化 session 恢复或离线回放。
- `P2-06-memory-update-and-backfill-tools.md`：补齐 memory 读/查/改/回填工具和 source log backfill 链路。
- `P2-07-auxiliary-model-router-expansion.md`：把辅助模型路由从 compaction 扩展到 memory/skills_hub/web_extract 等角色。
- `P2-08-cron-main-session-delivery.md`：让 `session=main` 的 cron 结果投递到真实活跃会话。
- `P2-09-agent-trace-schema-docs.md`：维护稳定事件 schema 文档和 schema 测试。
- `P2-10-evaluation-and-replay-tools.md`：建立评估和失败样本回放工具链。
- `P2-11-local-model-discovery.md`：实现 Ollama/vLLM 显式模型发现和配置片段生成。
- `P2-13-web-permission-approval-flow.md`：补齐 Web UI 的权限确认回传闭环。
- `P2-14-readonly-tool-parallelism.md`：在 AgentRuntime 内部并发执行同轮只读工具调用，不新增 batch tool。
- `P2-15-mcp-lifecycle-cleanup.md`：明确 MCP manager 生命周期，避免 server 进程泄漏。
- `P2-16-subagent-worktree-isolation.md`：给可写子 Agent 增加 worktree/tempdir 隔离。
- `P2-17-plugin-manifest-installer.md`：定义 Bamboo plugin manifest 和安装/卸载链路。

## 实施原则

- 每次只做一个需求，避免跨模块大面积重构。
- 已有能力优先复用：工具走 `ToolRegistry`，审批走 `PermissionPolicy`，委派走 `SubagentRuntime`，可复用流程走 `Command` 或 `Skill`。
- 新运行时能力继续接入主链路：`TaskFactory -> TaskRuntime -> AgentRuntime -> EventBus`。
- 用户空间内容优先可配置，包内内容只作为默认模板。
