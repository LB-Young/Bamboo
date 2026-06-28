# P2-01 Subagent Runtime

## 目标

支持主 Agent 把部分任务委派给子 Agent，并把结果作为 tool result 回到主循环。

## 参考

- Hermes Agent：subagent sessions linked to parent。
- OpenClaw：embedded runner 支持 agentId、runtimeInfo、tools、contextFiles。
- Claude Code Source：main thread agent 和 custom agent prompt 有明确优先级。

## 配置建议

```yaml
subagents:
  code-reviewer:
    description: "审查代码风险和测试缺口"
    model: deepseek-chat
    tools: [read, grep, glob]
    prompt: prompts/subagents/code-reviewer.md
```

## 实现步骤

1. 实现 `SubagentRegistry`。
2. 实现 `SubagentRuntime`，可复用 AgentRuntime 但有独立 session。
3. 新增 `subagent_run` tool。
4. subagent metadata 记录 parent_session_id、parent_task_id。
5. 默认只给只读工具。
6. 输出结构包含 summary、findings、files_touched、confidence。

## 验收标准

- 主 Agent 能调用 subagent_run。
- subagent 失败不会直接失败主任务。
- subagent 结果回到主 Agent 上下文。
- 子会话可追踪但默认不干扰主会话列表。

## 非目标

- 不支持并行多 subagent。
- 不给 subagent 默认写权限。
