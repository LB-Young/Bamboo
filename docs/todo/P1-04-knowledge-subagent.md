# P1-04 Knowledge Subagent

## 当前状态

未完成。

Subagent Runtime 已完成，但尚未用于 memory 知识沉淀。本条目只做“每轮结束后更新 knowledge md”，不要重复实现通用 subagent runtime。

## 目标

每轮对话结束后，调用专用 subagent 把本轮完整 turn 抽象成稳定知识，并更新对应 md knowledge。

## 背景

Memory knowledge 不应该完全依赖主 Agent 顺手维护。需要独立的 `KnowledgeSubagent` 专注做知识抽象，避免影响主任务回答。

## 依赖

- `P1-01-memory-source-log.md`
- `P1-02-memory-knowledge-layer.md`

## 输入

- 本轮 user message
- assistant 最终回复
- tool calls 和关键 tool results 摘要
- 本轮新增/修改文件列表
- 当前 scope 下已有 knowledge md 内容
- session_id/task_id

## 输出

- 要更新的 md 文件列表
- 每个文件的 patch 或新内容
- 不需要沉淀的原因
- 来源引用信息

## 实现步骤

1. 新增 `bamboo/memory/knowledge_subagent.py`。
2. 复用现有 `SubagentRuntime`，新增一个内置 `knowledge-curator` subagent 配置。
3. 先实现同步调用，后续可改成后台任务。
4. 使用单独配置的 memory/compaction 模型；未配置时复用主模型。
5. prompt 明确要求只沉淀稳定事实，不复制大段工具输出。
6. patch 写临时文件并校验，再原子替换 md。
7. 更新失败只记录事件，不影响主任务完成。

## 修改文件

- `bamboo/runtime/task_runtime.py`
- `bamboo/subagents/buildin/*.yaml`
- `bamboo/helpers/constant.py`

## 新增文件

- `bamboo/memory/knowledge_subagent.py`
- `bamboo/subagents/buildin/knowledge-curator.yaml`
- `tests/test_knowledge_subagent.py`

## 验收标准

- 每轮结束后能更新对应 scope 的 md knowledge。
- 不相关闲聊不会污染 knowledge。
- 更新内容能追溯 session_id/task_id。
- 写坏 md 时能回滚或保留原文件。

## 非目标

- 不重复实现通用 subagent runtime。
- 不接外部 memory provider。
