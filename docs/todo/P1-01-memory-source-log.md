# P1-01 Memory Source Log

## 目标

建立完整对话源日志层，作为长期记忆的事实底账。

## 背景

用户希望 chat/project 都完整保存每轮对话到 jsonl，但新的 query 不应该优先直接检索这些原始日志。源日志只负责完整、可追溯、不可丢失。

## 依赖

- `P0-05-session-store-and-trace.md`

## 存储结构

```text
~/.bamboo/memory/
  chat/sessions/{date}/{session_id}/messages.jsonl
  projects/{project_hash}/sessions/{session_id}/messages.jsonl
```

可复用 session store 的 messages，也可以在 memory 下建立索引或软链接。

## 实现步骤

1. 定义 `MemoryScope`：`chat` 或 `project:{project_hash}`。
2. 每轮结束后把完整 turn 写入源日志。
3. turn 至少包含 user message、assistant answer、tool calls、tool results 摘要、task_id、session_id、timestamp。
4. 对敏感信息做可配置脱敏。
5. 提供 `search_source_logs(query, scope)` 的最小实现，先用文本检索。

## 验收标准

- project 模式源日志按项目隔离。
- chat 模式源日志进入全局 chat scope。
- 每轮对话都能追溯到源日志。
- 源日志不直接进入 system prompt。

## 非目标

- 不实现 md 知识抽象。
- 不实现向量检索。
