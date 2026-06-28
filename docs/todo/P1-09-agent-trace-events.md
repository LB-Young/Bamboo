# P1-09 Agent Trace Events

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

1. BaseEvent 增加 event_id、timestamp、parent_event_id。
2. EventBus 支持 `subscribe(pattern)`。
3. `TraceRecorder` 写入 events.jsonl。
4. LLM request/response 增加脱敏事件。
5. CLI 增加 `--debug-events`。
6. docs 维护 event schema。

## 验收标准

- 一次任务可以从 events.jsonl 看到完整链路。
- UI 可以只订阅 text/tool。
- permission、memory、skill、subagent 事件有预留分类。

## 非目标

- 不做图形化 trace viewer。
