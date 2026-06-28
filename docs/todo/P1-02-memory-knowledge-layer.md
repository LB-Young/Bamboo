# P1-02 Memory Knowledge Layer

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

1. 新增 knowledge 模板，放在包内并在 init 时复制到用户空间。
2. `MemoryManager.load_prompt_context(task)` 读取当前 scope 的关键 md。
3. 初期可以全量读取小文件，后续再做段落检索。
4. md 中每条关键知识建议带来源标识：`source: session_id/task_id`。
5. 支持用户手动编辑 md，下一轮立即生效。

## 验收标准

- project 模式只读取当前项目 knowledge。
- chat 模式读取全局 chat knowledge。
- 修改 md 后下一轮 prompt 生效。
- knowledge 文件不存在时自动创建模板或跳过，不影响运行。

## 非目标

- 不自动更新 knowledge，这由 KnowledgeSubagent 需求实现。
