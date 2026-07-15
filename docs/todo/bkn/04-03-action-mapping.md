# Feature 4.3：Action 元数据到 Tool/Workflow/MCP 的映射

## 目标

把 BKN action 元数据映射到现有 Tool、Workflow 或 MCP，但不绕过权限系统。

## 需要干什么

- `bkn_list_actions` 列出当前平台、当前实体可用 actions。
- `bkn_action_prepare` 只生成建议调用，不执行。
- 真正执行仍走现有 Tool/Workflow/MCP 和 permission 流程。

## 为什么

- BKN 应声明“这个对象能做什么”，但不应该绕过 Bamboo 既有工具审批。
- prepare/execute 分离能让模型先解释风险，再请求用户确认。

## 需要改什么文件

- `bamboo/tools/buildin/__init__.py`
  - 注册 action 相关工具。
- `bamboo/bkn/models.py`
  - `ActionSpec`
- `bamboo/bkn/loader.py`
  - snapshot available_actions 过滤。

## 需要增加什么文件

- `bamboo/tools/buildin/bkn_list_actions.py`
- `bamboo/tools/buildin/bkn_action_prepare.py`
- `tests/test_bkn_action_tools.py`

## 测试

- 未在 manifest allowlist 的 action 不返回。
- prepare 输出目标 tool/workflow、参数 schema 和风险说明。
- 不直接执行外部动作。

## 验收标准

- Agent 能根据 BKN 上下文建议下一步调用哪个现有工具，但执行仍由现有 permission 管。
