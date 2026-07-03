# Bamboo Agent 剩余 Todo

本目录只保留当前还没有完成的开发项。已经完成的能力不再保留 todo，避免后续重复实现。

## 已完成并移除的条目

- RuntimeContextBuilder：已由 `bamboo/runtime/runtime_context.py` 实现。
- Prompt Section Pipeline：已由 `bamboo/prompts/system_prompt.py` 和 `bamboo/runtime/prompt.py` 实现基础分段。
- Permission Policy：已由 `bamboo/security/permission_policy.py`、resolver、audit 和 AgentRuntime 接入实现。
- Skills Hub / Guard：已由 `bamboo/skills/hub.py`、`guard.py`、CLI 和 lock/audit 实现。
- Subagent Runtime：已由 `bamboo/runtime/subagent_runtime.py`、`bamboo/tools/buildin/subagent_run.py` 和内置 subagent 配置实现。

## P0：运行时稳定性补齐

1. `P0-05-session-store-and-trace.md`

## P1：长期上下文和模型可靠性

2. `P1-01-memory-source-log.md`
3. `P1-02-memory-knowledge-layer.md`
4. `P1-03-memory-query-retrieval.md`
5. `P1-04-knowledge-subagent.md`
6. `P1-06-model-fallback-and-auxiliary-router.md`
7. `P1-07-reactive-compact.md`
8. `P1-08-provider-specific-prompt.md`
9. `P1-09-agent-trace-events.md`

## P2：自动化扩展

10. `P2-02-workflow-runner.md`
11. `P2-03-cron-heartbeat.md`

## 实施原则

- 每次只做一个需求，避免跨模块大面积重构。
- 已有能力优先复用：工具走 `ToolRegistry`，审批走 `PermissionPolicy`，委派走 `SubagentRuntime`，可复用流程走 `Command` 或 `Skill`。
- 新运行时能力继续接入主链路：`TaskFactory -> TaskRuntime -> AgentRuntime -> EventBus`。
- 用户空间内容优先可配置，包内内容只作为默认模板。
