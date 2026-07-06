# P2-09 Agent Trace Schema Docs

## 排期信息

- 建议顺序：2
- 建议阶段：P0 - 安全闭环和运行时基础
- 重要程度：高
- 优先级：P0
- 依赖关系：依赖现有 EventBus、`BaseEvent`、`TraceRecorder` 和各类事件 dataclass。

## 功能定位

这是 trace 事件的对外契约固化能力。当前事件已经能产生和持久化，但缺少稳定 schema 文档和测试约束，Web、replay、eval、外部工具都需要读源码才能理解事件。该需求完成后，事件字段、兼容规则和新增事件更新要求会变成可维护的工程约束。

## 当前状态

部分完成。

当前已经有：

- `BaseEvent.event_id/timestamp/session_id/task_id/parent_event_id`
- EventBus pattern subscribe
- LLM request/response 脱敏事件
- TraceRecorder 写入 `events.jsonl`

缺失的是一份稳定的事件 schema 文档和 schema 测试，roadmap 中提到的统一分类也没有完全沉淀成文档。

## 目标

为 Agent trace 事件建立可维护的 schema 文档，让 Web/UI/replay/外部工具可以稳定消费事件。

## 需要新增的文件

- `docs/agent-trace-events.md`
  - 记录事件分类。
  - 记录每类事件字段。
  - 记录兼容规则，例如 `tool-call` 与 `tool.*` pattern 的关系。

## 需要修改的文件

- `bamboo/helpers/constant.py`
  - 给新增事件补齐 `to_dict()` 字段一致性。
  - 必要时补 `agent.*` / `context.*` 类事件。
- `tests/test_agent_trace_schema.py`
  - 验证关键事件 `to_dict()` 包含必需字段。
  - 验证文档中列出的事件类型都存在。

## 验收标准

- docs 中能查到所有 EventBus 对外事件。
- replay/web 不需要读源码也能按 schema 消费事件。
- 新增事件时测试会提醒更新文档。
