# P2-14 Readonly Tool Parallelism

## 当前状态

未完成。

项目没有 `batch` 工具，这是正确方向；但 `AgentRuntime` 也还没有实现“同一轮多个只读 tool calls 受控并发执行”。

## 目标

在不新增 `batch` tool 的前提下，让同一轮模型返回的多个 read-only tool calls 可以并发执行，提高读取/搜索类任务效率。

## 需要修改的文件

- `bamboo/runtime/agent_runtime.py`
  - 在 `_act()` 中识别同一轮 tool calls。
  - 如果全部 tool 的实际风险都是 `read`，并发执行。
  - 每个 tool call 仍单独走 PermissionPolicy、Audit、EventBus。
  - write/network/unknown/execute 保持顺序执行。
- `bamboo/security/permission_policy.py`
  - 暴露一个可复用风险评估方法，避免并发判断和执行审批逻辑不一致。
- `tests/test_agent_readonly_parallel.py`

## 验收标准

- 多个 read-only 工具可以并发执行。
- 任意一个非 read 工具存在时整轮保持顺序。
- 并发执行仍产生完整 `ToolCallEvent`、`Permission*Event`、`ToolAuditEvent`、`ToolResultEvent`。
- 工具结果写入 session 的顺序稳定可预测。
