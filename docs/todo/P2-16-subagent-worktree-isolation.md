# P2-16 Subagent Worktree Isolation

## 当前状态

未完成。

SubagentRuntime 已有第一版，同进程执行、工具权限收窄。文档中提到的高级开发体验包括 worktree 隔离子 Agent，目前还没有实现。

## 目标

让允许写操作的子 Agent 在独立 worktree 或临时 workspace 中执行，避免多个 Agent 同时修改同一工作区造成冲突。

## 需要修改的文件

- `bamboo/runtime/subagent_runtime.py`
  - 支持为特定 subagent 创建 worktree/workspace。
  - 子任务完成后返回 diff/summary。
- `bamboo/subagents/models.py`
  - 增加 `workspace_mode`：`shared/read_only/worktree/tempdir`。
- `bamboo/subagents/registry.py`
  - 校验写权限 subagent 必须声明隔离策略。
- `bamboo/tools/buildin/subagent_run.py`
  - 输出 worktree path、diff summary。
- `tests/test_subagent_worktree_isolation.py`

## 验收标准

- 只读 subagent 继续使用共享 workspace。
- 写权限 subagent 默认需要 worktree/tempdir。
- 子 Agent 修改不会直接污染主工作区，除非用户显式合并。
- 冲突和失败能保留隔离目录用于排查。
