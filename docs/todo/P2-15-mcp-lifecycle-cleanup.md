# P2-15 MCP Lifecycle Cleanup

## 排期信息

- 建议顺序：2
- 建议阶段：P0 - 安全闭环和运行时基础
- 重要程度：极高
- 优先级：P0
- 依赖关系：依赖现有 `MCPManager`、`RuntimeContextBuilder` 和 `TaskRuntime` 生命周期。

## 功能定位

这是 MCP 外部进程的生命周期治理能力。当前 MCP 可以启动和注册工具，但任务完成、异常或取消时还没有统一 cleanup hook，存在 server 进程遗留的风险。该需求需要明确 MCP 是 task 级拥有还是进程级复用，并保证 start/stop 都可观测、可重复、可清理。

## 当前状态

部分完成。

当前已有 `MCPManager.stop_all()`，也能在 `RuntimeContextBuilder` 中启动并注册 MCP tools。但 TaskRuntime 没有统一 runtime cleanup hook，MCP server 生命周期还没有和 task/session 生命周期清晰绑定。

## 目标

明确 MCP server 是进程级复用还是 task 级启动，并保证异常、取消、完成时都能关闭或复用，不留下孤儿进程。

## 需要修改的文件

- `bamboo/runtime/runtime_context.py`
  - 给 `RuntimeContext` 增加 `cleanup()` 或 `close()`。
  - 记录当前 context 是否 owns MCP manager。
- `bamboo/runtime/task_runtime.py`
  - 在 task completed/failed/cancelled 的 finally 中调用 cleanup hook。
  - 如果 MCP 是进程级复用，则只记录引用，不关闭；需要显式 shutdown。
- `bamboo/tools/mcp/manager.py`
  - 增加幂等 shutdown。
  - 记录 start/stop errors。
- `bamboo/helpers/constant.py`
  - 可选新增 `MCPServerStartEvent`、`MCPServerStopEvent`、`MCPToolDiscoveredEvent`。
- `tests/test_mcp_lifecycle.py`

## 验收标准

- task 异常时 MCP 进程不会泄漏。
- `stop_all()` 可重复调用且不报错。
- MCP server 启动失败时错误可见，并写入 trace/audit。
- 生命周期策略在文档中明确。
