# P2-02 Workflow Runner

## 目标

支持用户定义多步骤工作流，让 Agent、工具和固定步骤可以顺序执行。

## 背景

Bamboo 已有 workflows 配置目录，但 runtime 未接入。

## 配置建议

```yaml
workflows:
  daily-review:
    steps:
      - agent: main
        prompt: "总结今天项目变化"
      - tool: write
        args:
          file_path: "daily.md"
```

## 实现步骤

1. 定义 workflow schema。
2. 实现 `WorkflowRegistry`，读取 buildin 和 userspace workflows。
3. 实现 `WorkflowRunner`，支持顺序步骤。
4. 支持变量传递：上一步输出作为下一步输入。
5. 支持失败策略：stop/continue/retry。
6. 工作流执行必须复用 TaskRuntime 和 PermissionPolicy。

## 验收标准

- 能执行一个两步 workflow。
- 失败策略生效。
- workflow 事件写入 trace。
- 用户空间新增 workflow 后下一次可用。

## 非目标

- 不做复杂 DAG。
- 不做可视化编辑器。
