# Feature 4.3：BKN 私有 Action 脚本和工作流

## 目标

让每个 BKN 平台拥有自己的 action/workflow/script 目录。Action 执行不复用 main agent 的 Tool/Workflow/MCP 注册表，而是由 BKN action runner 在当前平台 BKN 目录内通过 bash 子进程执行受控脚本。

## 需要干什么

- 每个 BKN 平台目录支持私有执行资源：
  - `actions/*.yaml`：action 元数据、参数 schema、脚本入口、风险级别。
  - `workflows/*/WORKFLOW.md`：当前 BKN 专属工作流说明。
  - `scripts/*`：当前 BKN 专属可执行脚本。
- `schema.json` 的 `action_registry` 不再指向 main agent 的 tool name，而是指向当前平台目录下的 action id。
- `bkn_list_actions` 列出当前平台、当前实体可用 actions。
- `bkn_action_prepare` 只生成执行计划、参数校验结果、目标脚本路径和风险说明，不执行。
- `bkn_action_execute` 通过 bash 子进程执行当前 BKN 私有脚本。
- 所有执行都必须限制在当前 BKN 平台目录内，不允许引用 main agent tools/workflows，也不允许跨平台目录执行脚本。
- `bkn_action_execute` 必须是 `risk_level="execute"` 或更高，并走现有 permission 流程。

## 为什么

- BKN 的 action 是业务平台能力，应该随平台 BKN 一起版本化、审核和迁移，而不是污染 main agent 的全局工具表。
- main agent 的 Tool/Workflow 是通用能力；BKN action 是平台私有业务能力，两者混用会导致权限边界和所有权不清。
- bash 子进程执行模型简单、可审计，也和个人开发者本地脚本工作流匹配。
- prepare/execute 分离能让模型先解释风险，再请求用户确认。

## 需要改什么文件

- `bamboo/tools/buildin/__init__.py`
  - 注册 action 相关工具。
- `bamboo/bkn/models.py`
  - 增加 `BknActionSpec` 或扩展现有 `BKNAction`，支持 `entrypoint`、`cwd`、`arguments_schema`、`risk_level`。
- `bamboo/bkn/loader.py`
  - snapshot available_actions 过滤。
- `bamboo/security/permission_policy.py`
  - 如有必要，确认 `bkn_action_execute` 按 execute/write/network 风险触发审批。

## 需要增加什么文件

- `bamboo/tools/buildin/bkn_list_actions.py`
- `bamboo/tools/buildin/bkn_action_prepare.py`
- `bamboo/tools/buildin/bkn_action_execute.py`
- `bamboo/bkn/action_runner.py`
- `tests/test_bkn_action_tools.py`
- `tests/fixtures/bkn/<platform>/actions/*.yaml`
- `tests/fixtures/bkn/<platform>/scripts/*`

## 测试

- 未在 manifest allowlist 的 action 不返回。
- prepare 输出 action id、目标脚本路径、参数 schema、cwd、风险说明。
- action 入口必须 resolve 后仍在当前 BKN platform 目录内；越权路径拒绝。
- `bkn_action_execute` 不允许调用 main agent ToolRegistry 或全局 workflow。
- `bkn_action_execute` 通过 bash 子进程执行 fixture 脚本，并返回 stdout/stderr/exit_code。
- `bkn_action_execute` 是 execute risk，需要触发现有 permission 流程。
- 脚本不存在、参数不满足 schema、manifest status 不可写/不可用时失败。

## 验收标准

- Agent 能根据 BKN 上下文建议并准备某个当前平台私有 action。
- 用户批准后，BKN action runner 能只在当前 BKN 平台目录下执行对应脚本。
- 执行结果有清晰的 stdout/stderr/exit_code 和 audit 信息。
