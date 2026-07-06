# P2-12 OS Sandbox Runner

## 当前状态

未完成。

`bamboo/security/sandbox.py` 目前只有 `SandboxConfig` 和 `SandboxResult` 占位，没有真正接入命令执行。

## 目标

为高风险 shell/外部进程执行提供可配置 OS sandbox。审批层仍然是第一道防线，sandbox 是第二道隔离层。

## 需要修改的文件

- `bamboo/security/sandbox.py`
  - 增加 `run_sandboxed(command, config)`。
  - macOS 优先支持 `sandbox-exec` profile。
  - Linux 优先支持 `bwrap`，可选 `unshare` fallback。
  - 支持 `writable_roots`、env allowlist、network 开关。
- `bamboo/tools/buildin/bash.py`
  - 在配置启用时通过 sandbox runner 执行命令。
  - 把 sandbox 结果写入 `ToolResult.metadata`。
- `bamboo/security/audit_log.py`
  - 审计记录中增加 sandbox enabled/profile/result。
- `bamboo/configs/tools.yaml`
  - 增加 sandbox 配置示例。
- `tests/test_sandbox_runner.py`

## 策略建议

- 默认开发环境 `fail_open=false` 更安全；如果为了兼容，可显式配置 `fail_open=true`，但必须写 audit。
- sandbox 不应该绕过 PermissionPolicy；只有审批 allow 后才进入 sandbox 执行。

## 验收标准

- 启用 sandbox 后 bash 命令通过 sandbox runner 执行。
- writable roots 以外的写入被阻止或返回清晰错误。
- sandbox 不可用时按配置 fail-open/fail-closed。
- 每次 sandbox 执行写入审计 metadata。
