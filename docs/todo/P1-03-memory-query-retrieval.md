# P1-03 Memory Query Retrieval

## 目标

实现历史信息检索链路：先查 md knowledge，不足时再查 jsonl 源日志。

## 背景

用户明确希望新的问题需要历史信息时，优先从抽象知识中检索，只有没有命中时才回源检索完整 jsonl。

## 依赖

- `P1-01-memory-source-log.md`
- `P1-02-memory-knowledge-layer.md`

## 检索链路

```text
new query
  -> resolve memory scope
  -> search knowledge md files
  -> if enough: inject relevant knowledge into context
  -> if not enough: search source jsonl logs
  -> if source logs found: inject source snippets
  -> optionally trigger knowledge backfill
```

## 实现步骤

1. 实现 `MemoryManager.search_knowledge(query, scope)`。
2. 实现 `MemoryManager.search_source_logs(query, scope)`。
3. 先用关键词/BM25 风格文本检索，后续再换向量。
4. 定义 `MemoryContext`，包含 source、content、score、origin。
5. `AgentPromptBuilder` 接收 memory context 并拼到 prompt section。
6. 如果 source log 命中但 knowledge 未覆盖，记录 `memory_backfill_needed=true`。

## 验收标准

- query 能优先命中 md knowledge。
- md 无命中时才读取 jsonl。
- 注入 prompt 的内容带来源说明。
- 检索失败不影响主任务执行。

## 非目标

- 不实现复杂 embedding。
- 不自动更新 knowledge。
