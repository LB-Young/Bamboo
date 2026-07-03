# P1-09 Agent Trace Events

## 当前状态

部分完成。

`BaseEvent` 已有 `event_id` 和 `timestamp`，`EventBus.subscribe()` 已支持按 event type 过滤。但还缺 `parent_event_id`、pattern 订阅、`TraceRecorder`、LLM 脱敏事件、debug CLI 和事件 schema 文档。

## 目标

把事件系统升级为标准 Agent Trace，支持调试、回放和 UI 订阅。

## 参考

- Auton：EventBus 订阅 text/tool/compact。
- Hermes Agent：events_poll/events_wait/permissions_list_open。
- Claude Code Source：query loop yield stream/tool/recovery 事件。

## 事件分类

```text
task.*
agent.*
llm.*
tool.*
context.*
memory.*
skill.*
subagent.*
permission.*
```

## 实现步骤

1. `BaseEvent` 增加 `parent_event_id`。
2. EventBus 支持 `subscribe(pattern="tool.*")`。
3. 新增 `TraceRecorder` 写入 `events.jsonl`，复用 `P0-05` 的 session store。
4. LLM request/response 增加脱敏事件。
5. CLI 增加 `--debug-events`。
6. docs 维护 event schema。

## 修改文件

- `bamboo/helpers/utils.py`
- `bamboo/factory/event_bus.py`
- `bamboo/runtime/agent_runtime.py`
- `bamboo/adapters/cli/main.py`
- `bamboo/adapters/web/app.py`

## 新增文件

- `bamboo/runtime/trace_recorder.py`
- `docs/event-schema.md`
- `tests/test_agent_trace_events.py`

## 验收标准

- 一次任务可以从 events.jsonl 看到完整链路。
- UI 可以只订阅 text/tool。
- permission、memory、skill、subagent 事件有预留分类。

## 非目标

- 不做图形化 trace viewer。
