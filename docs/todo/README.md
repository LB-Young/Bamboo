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
- Agent Trace Events：已由 `parent_event_id`、EventBus pattern 订阅、LLM 脱敏事件、TraceRecorder 和事件 schema 文档实现。
- Workflow Runner：已改为 skill-like workflow 文档包，通过 `workflow_load` / `workflow_run` 工具读取说明并执行声明脚本。

## P2：自动化扩展

1. `P2-03-cron-heartbeat.md`

## 实施原则

- 每次只做一个需求，避免跨模块大面积重构。
- 已有能力优先复用：工具走 `ToolRegistry`，审批走 `PermissionPolicy`，委派走 `SubagentRuntime`，可复用流程走 `Command` 或 `Skill`。
- 新运行时能力继续接入主链路：`TaskFactory -> TaskRuntime -> AgentRuntime -> EventBus`。
- 用户空间内容优先可配置，包内内容只作为默认模板。
