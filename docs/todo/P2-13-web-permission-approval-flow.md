# P2-13 Web Permission Approval Flow

## 当前状态

部分完成。

Web adapter 已经能把 `PermissionRequestEvent` / `PermissionResultEvent` 转成 SSE 事件发给前端，但还没有用户点击批准/拒绝后回传给运行时的闭环。当前 Web 入口仍主要依赖非交互 resolver，ask 类权限会被拒绝或无法完成交互确认。

## 目标

在 Web UI 中实现和 CLI 类似的权限审批体验：工具请求权限时，前端显示确认框，用户批准或拒绝后运行时继续。

## 需要修改的文件

- `bamboo/security/permission_resolver.py`
  - 新增 Web/async approval resolver。
  - 支持按 `session_id/task_id/tool_call_id` 等待审批结果。
- `bamboo/adapters/web/app.py`
  - 增加审批结果提交 API，例如 `POST /api/permissions/{request_id}`。
  - Web session 创建时注入 Web permission resolver。
- `bamboo/adapters/web/static/app.js`
  - 收到 `permission_request` 事件后展示确认 UI。
  - 将 allow/deny 回传 API。
- `bamboo/adapters/web/static/styles.css`
  - 增加权限确认 UI 样式。
- `tests/test_web_permission_flow.py`

## 验收标准

- Web 中触发 `write/network/unknown` 工具时出现确认 UI。
- 用户批准后工具继续执行。
- 用户拒绝后工具结果以 tool error 进入会话。
- 审批只对当前 `session_id/task_id/tool_call_id` 有效，不能跨 session 复用。
