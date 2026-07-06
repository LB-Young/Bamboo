# Agent Trace Events

本文档定义 Bamboo EventBus 和 TraceRecorder 对外暴露的事件 schema。Web UI、replay、eval、外部调试工具应按本文档消费事件，不应依赖 Python dataclass 内部实现。

## 兼容规则

- 事件 `type` 使用 kebab-case，例如 `tool-call`、`llm-response`。
- EventBus pattern 订阅同时兼容 `.` 和 `-`：`tool.*` 可以匹配 `tool-call`、`tool-result`、`tool-error`、`tool-audit`。
- 新增事件必须同时更新本文档和 `tests/test_agent_trace_schema.py`。
- 已发布字段只能追加，不能重命名或改变语义；废弃字段应先保留并在文档中标记 deprecated。
- LLM trace 事件只记录脱敏元数据，不记录完整 prompt、用户正文、模型正文或工具结果全文。
- TraceRecorder 按 `session_id` 和可选 `task_id` 过滤事件，并把 `event.to_dict()` 追加到 `events.jsonl`。

## 公共字段

所有事件都包含以下字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 事件类型。 |
| `session_id` | string | 会话 id。 |
| `timestamp` | number | Unix timestamp，单位秒。 |
| `event_id` | string | 事件唯一 id。 |
| `parent_event_id` | string/null | 父事件 id，用于表达 request/response、开始/结束等链路关系。 |
| `step_id` | string/null | 所属步骤 id。 |
| `task_id` | string/null | 当前任务 id。 |
| `plat_info` | string/null | 平台扩展信息。 |

## 事件分类

| 分类 | 事件前缀 | 用途 |
| --- | --- | --- |
| text | `text-*` | 助手文本输出。 |
| reasoning | `reasoning-*` | 推理文本输出。 |
| llm | `llm-*` | 脱敏模型请求和响应元数据。 |
| tool | `tool-*` | 工具调用、结果、错误和审计。 |
| permission | `permission-*` | 工具权限请求和决策。 |
| task | `task-*` | 任务创建、状态、快照、停止。 |
| session | `session-*` | 会话状态和上下文压缩。 |
| step | `step-*` | 可展示执行步骤。 |
| cron | `cron-*` | 定时任务和 heartbeat。 |
| subagent | `subagent-*` | 子 Agent 启动和完成。 |
| memory | `memory-*` | knowledge 更新和错误。 |
| plan | `plan-*` | 计划创建、确认、执行和取消。 |
| workflow | `workflow-*` | workflow 执行和断点。 |
| todo | `todo-*` | Todo 列表更新。 |
| audit | `audit` | 通用审计事件。 |

## 事件 Schema

| Type | Class | Category | Fields |
| --- | --- | --- | --- |
| `audit` | `AuditEvent` | audit | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, action, tool_name, params, result, approved` |
| `cron-heartbeat` | `CronHeartbeatEvent` | cron | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, tick, due_jobs` |
| `cron-job-complete` | `CronJobCompleteEvent` | cron | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, job_name, run_id, status, attempt, error, delivery, target_session_id, target_record_dir` |
| `cron-job-start` | `CronJobStartEvent` | cron | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, job_name, run_id, attempt, delivery, target_session_id, target_record_dir` |
| `llm-request` | `LLMRequestEvent` | llm | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, role, model_name, provider, prompt_profile, message_count, tool_count, system_prompt_chars, input_chars` |
| `llm-response` | `LLMResponseEvent` | llm | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, role, model_name, provider, response_model, finish_reason, output_chars, tool_call_count, usage, success, error_type, error` |
| `memory-knowledge-error` | `KnowledgeUpdateErrorEvent` | memory | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, scope, file, reason` |
| `memory-knowledge-update` | `KnowledgeUpdateEvent` | memory | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, scope, file, operation, status, reason` |
| `permission-request` | `PermissionRequestEvent` | permission | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, tool_name, tool_call_id, risk_level, reason, requires_confirmation` |
| `permission-result` | `PermissionResultEvent` | permission | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, tool_name, tool_call_id, decision, approved, risk_level, reason` |
| `plan-cancel` | `PlanCancelEvent` | plan | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, plan_id, reason` |
| `plan-confirm` | `PlanConfirmEvent` | plan | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, plan_id, step_count` |
| `plan-start` | `PlanStartEvent` | plan | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, plan_id, task` |
| `plan-step` | `PlanStepExecuteEvent` | plan | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, plan_id, step_index, step_description` |
| `reasoning-delta` | `ReasoningDeltaEvent` | reasoning | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, delta` |
| `reasoning-finish` | `ReasoningFinishEvent` | reasoning | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, content, message_id` |
| `reasoning-start` | `ReasoningStartEvent` | reasoning | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, message_id` |
| `session-compact` | `SessionCompactEvent` | session | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, before_token_count, after_token_count, reason` |
| `session-status-change` | `SessionStatusChangeEvent` | session | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, status, reason` |
| `step-finish` | `StepFinishEvent` | step | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, step_index, summary, files_changed, token_used` |
| `step-start` | `StepStartEvent` | step | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, step_index` |
| `subagent-finish` | `SubagentFinishEvent` | subagent | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, subagent_name, child_task_id, child_session_id, parent_session_id, parent_task_id, status` |
| `subagent-start` | `SubagentStartEvent` | subagent | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, subagent_name, child_task_id, parent_session_id, parent_task_id, description` |
| `task-create` | `TaskCreateEvent` | task | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, title` |
| `task-snapshot` | `TaskSnapshotEvent` | task | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, snapshot` |
| `task-status-change` | `TaskStatusChangeEvent` | task | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, from_status, to_status` |
| `task-stop` | `TaskStopEvent` | task | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, stopped_task_id, reason` |
| `text-delta` | `TextDeltaEvent` | text | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, delta` |
| `text-finish` | `TextFinishEvent` | text | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, content, message_id` |
| `text-start` | `TextStartEvent` | text | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, message_id` |
| `todo-update` | `TodoUpdateEvent` | todo | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, todos, counts` |
| `tool-audit` | `ToolAuditEvent` | tool | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, tool_name, tool_call_id, risk_level, decision, approved, success, reason, error, duration_ms` |
| `tool-call` | `ToolCallEvent` | tool | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, tool_name, tool_input, tool_call_id` |
| `tool-error` | `ToolErrorEvent` | tool | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, tool_name, tool_call_id, error` |
| `tool-result` | `ToolResultEvent` | tool | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, tool_name, tool_call_id, output, context_output, truncated, original_length, context_length, original_tokens, context_tokens` |
| `workflow-breakpoint` | `WorkflowBreakpointEvent` | workflow | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, run_id, workflow_id, reason` |
| `workflow-run-complete` | `WorkflowRunCompleteEvent` | workflow | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, run_id, workflow_id, status, duration_seconds` |
| `workflow-run-start` | `WorkflowRunStartEvent` | workflow | `type, session_id, timestamp, event_id, parent_event_id, step_id, task_id, plat_info, run_id, workflow_id` |

## Consumer Notes

- `tool-result.output` may be large and is intended for UI/log display. Prompt context uses `context_output` after budget processing.
- `llm-request` and `llm-response` intentionally omit raw message content.
- `permission-request` and `permission-result` are scoped by `session_id`, `task_id`, and `tool_call_id`.
- `audit` is a generic runtime audit event; durable tool-call audit records are also written by `ToolAuditLogger`.
