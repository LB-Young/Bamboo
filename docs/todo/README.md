# Bamboo Agent 剩余 Todo

本目录只保留当前还没有完成的开发项。已经完成的能力不再保留 todo，避免后续重复实现。

## 已完成并移除的条目

- RuntimeContextBuilder：已由 `bamboo/runtime/runtime_context.py` 实现。
- Prompt Section Pipeline：已由 `PromptSection` 对象模型、`SystemPromptBuilder.build_sections()`、runtime prompt section metadata 和 prompt hash 实现。
- Permission Policy：已由 `bamboo/security/permission_policy.py`、resolver、audit 和 AgentRuntime 接入实现。
- Skills Hub / Guard：已由 `bamboo/skills/hub.py`、`guard.py`、CLI 和 lock/audit 实现。
- Subagent Runtime：已由 `bamboo/runtime/subagent_runtime.py`、`bamboo/tools/buildin/subagent_run.py` 和内置 subagent 配置实现。
- Model Fallback And Auxiliary Router：已由 `bamboo/llms/router.py`、结构化 LLM 错误和 AgentRuntime fallback 接入实现。
- Reactive Compact：已由 `ContextCompactor.compact(force=True)`、`SessionCompactEvent.reason` 和 AgentRuntime reactive retry 实现。
- Provider Specific Prompt：已由 `ModelConfig.prompt_profile/capabilities`、provider prompt section 和 PromptBuilder 接入实现。
- Agent Trace Events：已由 `parent_event_id`、EventBus pattern 订阅、LLM 脱敏事件、TraceRecorder、`docs/agent-trace-events.md` 和 schema 测试实现。
- Workflow Runner：已改为 skill-like workflow 文档包，通过 `workflow_load` / `workflow_run` 工具读取说明并执行声明脚本。
- Cron And Heartbeat：已由 `bamboo/cron`、`bamboo cron`、`~/.bamboo/cron/jobs.yaml`、retry 和 jsonl 执行日志实现。
- OS Sandbox Runner：已由 `bamboo/security/sandbox.py`、`BashTool` sandbox 接入和 audit sandbox 元数据实现。
- Readonly Tool Parallelism：已由 `AgentRuntime` 同轮 read-only tool calls 并发执行和稳定顺序写回实现。
- Web Permission Approval Flow：已由 `WebPermissionResolver`、`POST /api/permissions/{request_id}` 和 Web 权限确认 UI 实现。
- MCP Lifecycle Cleanup：已由 `RuntimeContextBuilder.close()`、`TaskRuntime` finally cleanup 和幂等 `MCPManager.stop_all()` 实现。
- Memory Update And Backfill Tools：已由 `MemoryManager` 安全读写/回填接口、`memory_read` / `memory_search` / `memory_update` / `memory_backfill` 工具和 prompt 使用规则实现。
- Local Model Discovery：已由 Ollama `/api/tags`、vLLM `/v1/models` 显式发现、配置片段渲染、确认写入和备份机制实现。
- Cron Main Session Delivery：已由 cron `delivery=main` 目标 session 查找、恢复 follow-up 执行、Web/CLI cron 事件订阅和 session trace 事件持久化实现。
- Evaluation And Replay Tools：已由标准 eval case、replay fixture、live runner、报告渲染、`bamboo eval run/export` 和 `docs/eval.md` 实现。
- Auxiliary Model Router Expansion：已由 `LLMRouter.route_for_role()`、`RuntimeContext.client_for_role()`、role 级辅助模型配置和 compaction 独立 fallback 实现。
- Subagent Worktree Isolation：已由 `workspace_mode` 配置、`SubagentWorkspaceManager`、tempdir/worktree 隔离、diff metadata 和 `subagent_run` 输出实现。
- Plugin Manifest Installer：已由 `bamboo/plugins`、`bamboo plugin install/list/show/remove/validate`、plugin quarantine、scan、lock 和 audit 实现。

## 排期原则

- 当前剩余排期只保留 BKN 相关条目，详见 `docs/todo/bkn-milestones.md`。
- `P2-05 Session Resume And Replay` 的需求 md 已不存在，代码中已有 `--resume` / `replay` 相关实现入口；replay fixture 能力已并入 Evaluation And Replay Tools，不再单独排期。

## 当前剩余条目

- BKN（业务数据知识网络）：详见 `docs/todo/bkn-milestones.md`。

## 建议阶段

- BKN Milestone 1：只读 BKN MVP。
- BKN Milestone 2：平台级 BKN 图谱骨架。
- BKN Milestone 3：BKN 构建与审批闭环。
- BKN Milestone 4：数据源、算子和行动闭环。
- BKN Milestone 5：管理和可视化。

## 实施原则

- 每次只做一个需求，避免跨模块大面积重构。
- 已有能力优先复用：工具走 `ToolRegistry`，审批走 `PermissionPolicy`，委派走 `SubagentRuntime`，可复用流程走 `Command` 或 `Skill`。
- 新运行时能力继续接入主链路：`TaskFactory -> TaskRuntime -> AgentRuntime -> EventBus`。
- 用户空间内容优先可配置，包内内容只作为默认模板。
