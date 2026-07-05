---
name: daily-review
description: Summarize a project day and capture a lightweight local environment snapshot.
usage: |
  1. Call `workflow_load` with `name="daily-review"` to read this document.
  2. Call `workflow_run` with `name="daily-review"` and optional `arguments` for the focus.
dependencies:
  - bash tool
run:
  script: scripts/project_snapshot.sh
  cwd: .
  timeout: 60
  risk: read
---

# Daily Review Workflow

## 场景

用于快速整理一天内项目状态、当前目录信息和下一步建议。适合在项目模式下通过命令调用。

## 依赖

- `bash` tool
- 当前项目目录可读

## 使用方式

1. 先调用 `workflow_load` 读取本说明。
2. 再调用 `workflow_run`：

```json
{"name": "daily-review", "arguments": "修复任务运行时和事件 trace"}
```

## 执行步骤

`workflow_run` 会运行 `scripts/project_snapshot.sh`，输出当前目录的轻量快照。你可以基于输出继续总结 daily review。
