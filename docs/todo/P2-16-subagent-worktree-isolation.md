# P2-16 Subagent Worktree Isolation

## 一句话说明

让会写代码的 subagent 先在隔离工作区里改文件，主 Agent 看完 diff 后再决定是否合并，避免直接污染当前项目。

## 为什么要做

现在 SubagentRuntime 已经能启动子 Agent，也能限制它能用哪些工具。但如果一个 subagent 有写文件权限，它还是直接在主工作区修改文件。

这在以下场景有风险：

- 主 Agent 和 subagent 同时改同一批文件，容易互相覆盖。
- reviewer/verifier 类子 Agent 原本只应该检查，却可能误写文件。
- 多个 subagent 并行探索不同方案时，文件变更会混在一起。
- 子 Agent 写坏代码以后，主工作区需要人工回滚。

Worktree isolation 的目标是让“子 Agent 可以大胆尝试，但默认不直接改主工作区”。

## 做完以后是什么效果

典型流程：

1. 主 Agent 调用 `subagent_run`，指定一个可写 subagent。
2. Bamboo 为这个子任务创建独立 workspace。
3. 子 Agent 在隔离目录里执行、读写、测试。
4. 子 Agent 返回：
   - 结果摘要
   - 修改过的文件列表
   - diff summary
   - 隔离 workspace 路径
5. 主 Agent 或用户决定是否合并。

用户能看到类似结果：

```text
subagent completed: verifier
workspace: /tmp/bamboo-subagents/verifier-abc123
changed_files:
  - bamboo/runtime/foo.py
  - tests/test_foo.py
diff_summary:
  +42 -8
merge_required: true
```

## workspace 模式

建议支持 4 种模式：

| 模式 | 含义 | 适用场景 |
| --- | --- | --- |
| `shared` | 直接使用主工作区 | 兼容旧行为，不建议给写权限 subagent 用 |
| `read_only` | 只能读主工作区 | explorer、reviewer、planner |
| `tempdir` | 复制必要文件到临时目录 | 非 git 项目、一次性实验 |
| `worktree` | 用 git worktree 创建隔离分支/目录 | 代码修改、并行实现方案 |

## 不做什么

- 不自动把子 Agent 的 diff 合并回主工作区。
- 不替代权限系统；写操作仍然要遵守 ToolRegistry/PermissionPolicy。
- 不要求所有 subagent 都隔离。只读 subagent 可以继续共享 workspace。

## 需要解决的关键问题

### 1. 如何判断 subagent 是否需要隔离

可以从 subagent 配置判断：

- 如果 tools 只包含 read 风险工具：默认 `read_only` 或 `shared`。
- 如果 tools 包含 write/execute/network：必须显式声明 `workspace_mode`。
- 如果没有声明，默认拒绝或降级为 `read_only`。

### 2. 如何创建隔离目录

优先策略：

- git 项目：使用 `git worktree` 创建隔离 workspace。
- 非 git 项目：使用 `tempdir`，复制需要的文件。

### 3. 如何返回变更

子 Agent 完成后收集：

- changed files
- diff stat
- diff patch 路径
- workspace path
- 是否需要用户合并

### 4. 如何清理

默认不要立刻删除失败的隔离目录。

建议策略：

- 成功且无变更：自动清理。
- 成功且有变更：保留，等待合并/丢弃。
- 失败：保留，方便排查。

## 建议实现

### 1. subagent 配置模型

修改 `bamboo/subagents/models.py`：

- 增加 `workspace_mode` 字段：
  - `shared`
  - `read_only`
  - `tempdir`
  - `worktree`
- 增加可选 `keep_workspace_on_success`。

### 2. workspace 管理器

新增 `bamboo/runtime/subagent_workspace.py`：

- `SubagentWorkspace`
- `SubagentWorkspaceManager`
- 创建 tempdir/worktree。
- 收集 diff。
- 清理 workspace。

### 3. SubagentRuntime 接入

修改 `bamboo/runtime/subagent_runtime.py`：

- 根据 subagent definition 创建 workspace。
- 把 child task 的 project/root 指向隔离 workspace。
- 子任务结束后收集 diff summary。
- 返回结果里包含 workspace 元数据。

### 4. subagent_run 工具输出

修改 `bamboo/tools/buildin/subagent_run.py`：

- metadata 增加：
  - `workspace_mode`
  - `workspace_path`
  - `changed_files`
  - `diff_stat`
  - `merge_required`

### 5. registry 校验

修改 `bamboo/subagents/registry.py`：

- 写权限 subagent 如果没有 workspace 策略，给出 validation warning 或 error。

## 需要修改的文件

- `bamboo/subagents/models.py`
- `bamboo/subagents/registry.py`
- `bamboo/runtime/subagent_runtime.py`
- `bamboo/tools/buildin/subagent_run.py`

## 需要新增的文件

- `bamboo/runtime/subagent_workspace.py`
- `tests/test_subagent_worktree_isolation.py`

## 验收标准

- 只读 subagent 不创建 worktree，行为保持兼容。
- 写权限 subagent 可以在 tempdir/worktree 中修改文件。
- 子 Agent 修改不会直接出现在主工作区。
- `subagent_run` 返回 changed files 和 diff summary。
- 目标不是 git 仓库时，worktree 模式有清晰错误或自动降级到 tempdir。
- 失败时隔离目录被保留，并在结果里给出路径。

