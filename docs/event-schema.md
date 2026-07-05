# Bamboo Event Schema

## Base Fields

Every EventBus event inherits these fields:

| Field | Type | Notes |
| --- | --- | --- |
| `type` | string | Stable event name. Existing names use hyphen form, for example `tool-call`. |
| `session_id` | string | Conversation/session id. |
| `task_id` | string | Current task id when available. |
| `event_id` | string | Unique id for this event. |
| `parent_event_id` | string/null | Optional parent event id for request/response or nested trace relations. |
| `timestamp` | number | Unix timestamp. |
| `step_id` | string/null | Optional step id. |
| `plat_info` | string/null | Optional platform metadata. |

`SessionMemoryStore.append_event()` persists events to `events.jsonl` with `schema_version: 1` and `time`.

## Pattern Subscription

`EventBus.subscribe()` supports exact event names and wildcard patterns:

```python
event_bus.subscribe(handler, event_types={"tool-call", "tool-result"})
event_bus.subscribe(handler, patterns="tool.*")
event_bus.subscribe(handler, patterns={"text.*", "tool.*"})
event_bus.subscribe(handler, patterns="*")
```

Patterns use `fnmatch` semantics. For compatibility, hyphen event names are normalized while matching, so `tool.*` matches both future `tool.call` and current `tool-call`.

Recommended categories:

| Pattern | Includes |
| --- | --- |
| `task.*` | task lifecycle events |
| `agent.*` | reserved for detailed agent loop events |
| `llm.*` | redacted model request/response events |
| `tool.*` | tool call/result/error/audit events |
| `context.*` | reserved for context governance events |
| `memory.*` | memory and knowledge events |
| `skill.*` | reserved for skill events |
| `subagent.*` | subagent lifecycle events |
| `permission.*` | permission request/result events |
| `text.*` | assistant text streaming events |
| `session.*` | session status/compact events |
| `step.*` | high-level step events |

## LLM Events

LLM events are intentionally redacted. They do not include raw prompt text, user text, tool results, or assistant output.

### `llm-request`

| Field | Type | Notes |
| --- | --- | --- |
| `role` | string | Route role, currently `main`. |
| `model_name` | string | Bamboo model registration name. |
| `provider` | string | Provider name from model config. |
| `prompt_profile` | string | Active prompt profile. |
| `message_count` | int | Number of messages sent. |
| `tool_count` | int | Number of structured tools sent. |
| `system_prompt_chars` | int | Character count only. |
| `input_chars` | int | Character count only. |

### `llm-response`

| Field | Type | Notes |
| --- | --- | --- |
| `parent_event_id` | string | Links back to the corresponding `llm-request`. |
| `role` | string | Route role. |
| `model_name` | string | Bamboo model registration name. |
| `provider` | string | Provider returned by the response or active config on error. |
| `response_model` | string | Provider model id returned by the API. |
| `finish_reason` | string | Provider finish reason. |
| `output_chars` | int | Character count only. |
| `tool_call_count` | int | Number of tool calls returned. |
| `usage` | object | Token usage if provider returned it. |
| `success` | bool | Whether model call succeeded. |
| `error_type` | string | Structured error type on failure. |
| `error` | string | Truncated error summary on failure. |

## Trace Files

For sessions backed by `SessionMemoryStore`, `TaskRuntime` starts a `TraceRecorder` and writes:

- `events.jsonl`: EventBus events for the task/session.
- `tasks.jsonl`: task lifecycle snapshots.
- `turns.jsonl`: redacted user/assistant/tool source log.
- `compactions.jsonl`: context compaction before/after snapshots.

