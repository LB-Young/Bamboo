# P1-01 Memory Source Log

## 当前状态

部分完成。

`SessionMemoryStore` 已经保存完整 messages，但还没有明确 `MemoryScope`，也没有按 chat/project 建立可检索的源日志索引。此条目应复用现有 messages 落盘，不要另写一套重复日志系统。

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

1. 新增 `bamboo/memory/scope.py`，定义 `MemoryScope`：`chat` 或 `project:{project_hash}`。
2. 扩展 `SessionMemoryStore`，在每轮完成后写 `turns.jsonl`，不要只依赖单条 message。
3. turn 至少包含 user message、assistant answer、tool calls、tool results 摘要、task_id、session_id、timestamp。
4. 对敏感信息做可配置脱敏，复用 `bamboo/helpers/redact.py`。
5. 新增 `bamboo/memory/source_log.py`，提供 `search_source_logs(query, scope)` 的最小文本检索。

## 修改文件

- `bamboo/memory/session_store.py`
- `bamboo/factory/session.py`
- `bamboo/runtime/task_runtime.py`
- `tests/test_session_memory_store.py`

## 新增文件

- `bamboo/memory/scope.py`
- `bamboo/memory/source_log.py`
- `tests/test_memory_source_log.py`

## 验收标准

- project 模式源日志按项目隔离。
- chat 模式源日志进入全局 chat scope。
- 每轮对话都能追溯到源日志。
- 源日志不直接进入 system prompt。

## 非目标

- 不实现 md 知识抽象。
- 不实现向量检索。
