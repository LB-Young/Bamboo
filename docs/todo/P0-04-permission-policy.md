# P0-04 Permission Policy

## 目标

为工具调用增加权限判断和危险操作审批，尤其是 `bash/write/edit`。

## 背景

`RunParams` 已有 `permission` 和 `yes_all`，但 AgentRuntime 当前会直接执行模型返回的 tool call。需要建立统一权限层。

## 参考

- OpenCode：按 permission 控制工具能力可见性。
- Auton：SessionFactory 初始化工具时接收 permission mode。
- Hermes Agent：审批 session key 隔离、active-session guard。

## 范围

新增：

- `bamboo/security/permission_policy.py`
- 权限事件类型

调整：

- `ToolRegistry` 增加工具风险元数据。
- `AgentRuntime._execute_tool_call` 调用权限策略。
- CLI adapter 支持 ask 确认。

## 建议模型

```python
class PermissionDecision(str, Enum):
    allow = "allow"
    ask = "ask"
    deny = "deny"
```

风险级别：

- `read_only`
- `write`
- `execute`
- `network`
- `destructive`

## 实现步骤

1. 为内置工具配置默认 risk_level。
2. 实现 `PermissionPolicy.evaluate(tool_call, run_params)`。
3. 对 bash 命令做基础分类：读操作、写操作、删除操作、git 高危操作、网络操作。
4. EventBus 增加 `PermissionRequestEvent` 和 `PermissionResultEvent`。
5. CLI 收到 ask 后读取用户输入。
6. `yes_all=True` 时允许普通 ask，但 destructive 仍可配置强确认。

## 验收标准

- `read/glob/grep` 默认 allow。
- `write/edit/bash` 在 default 权限模式下 ask。
- `rm -rf`、`git reset --hard`、`git push --force` 默认 deny 或强确认。
- 审批事件包含 session_id/task_id/tool_call_id。

## 非目标

- 不实现复杂 shell AST 解析。
- 不做 GUI 权限弹窗。
