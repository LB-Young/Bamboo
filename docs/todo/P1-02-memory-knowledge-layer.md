# P1-02 Memory Knowledge Layer

## 当前状态

未完成。

当前只有源消息落盘，没有 `MemoryManager`，也没有 chat/project knowledge md 模板和 prompt 注入链路。

## 目标

在完整 jsonl 源日志之上建立 md 知识抽象层，作为 query 的首选历史上下文。

## 背景

直接检索完整历史对话容易噪声大、上下文成本高、重复信息多。需要把稳定事实、项目决策、用户偏好沉淀成可编辑 md 文件。

## 依赖

- `P1-01-memory-source-log.md`

## 目录结构

```text
~/.bamboo/memory/
  chat/knowledge/
    profile.md
    preferences.md
    recurring_topics.md
    decisions.md
    open_questions.md

  projects/{project_hash}/knowledge/
    overview.md
    architecture.md
    decisions.md
    coding_style.md
    bugs_and_fixes.md
    workflows.md
    open_questions.md
```

## 实现步骤

1. 新增 knowledge 模板，放在 `bamboo/memory/templates/`。
2. 新增 `bamboo/memory/manager.py`，实现 `MemoryManager.load_prompt_context(task)`。
3. `RuntimeContextBuilder` 创建 `MemoryManager` 并放入 `RuntimeContext.memory_manager`。
4. `AgentPromptBuilder` 或 system prompt 构建流程增加 memory section。
5. 初期可以全量读取小文件，后续再做段落检索。
6. md 中每条关键知识建议带来源标识：`source: session_id/task_id`。
7. 支持用户手动编辑 md，下一轮立即生效。

## 修改文件

- `bamboo/runtime/runtime_context.py`
- `bamboo/runtime/prompt.py`
- `bamboo/prompts/system_prompt.py`

## 新增文件

- `bamboo/memory/manager.py`
- `bamboo/memory/templates/chat/*.md`
- `bamboo/memory/templates/project/*.md`
- `tests/test_memory_knowledge_layer.py`

## 验收标准

- project 模式只读取当前项目 knowledge。
- chat 模式读取全局 chat knowledge。
- 修改 md 后下一轮 prompt 生效。
- knowledge 文件不存在时自动创建模板或跳过，不影响运行。

## 非目标

- 不自动更新 knowledge，这由 KnowledgeSubagent 需求实现。
