# Feature 1.5：`bkn_retrieval` 内置工具

## 目标

把 BKN 只读召回能力接入 Bamboo ToolRegistry，让 agent 能按需调用。

## 需要干什么

- 新增只读工具 `bkn_retrieval`。
- 支持 `bind_runtime_context(runtime_context, task)`。
- 从 `runtime_context.bkn_registry` 读取 registry。
- 缺少上下文时返回 `missing_runtime_context`。
- 限制 `limit` 和 `max_hops` 范围。

## 为什么

- Bamboo Agent 使用 ToolRegistry 暴露能力。BKN 第一版应作为普通只读工具接入，不应先改 prompt 注入机制。
- 复用 `memory_retrieve` 模式，降低运行时集成风险。

## 需要改什么文件

- `bamboo/tools/buildin/__init__.py`
  - import `BKNRetrievalTool`。
  - `create_builtin_tools()` 返回列表加入 `BKNRetrievalTool()`。
- `bamboo/runtime/runtime_context.py`
  - `RuntimeContext` 增加 `bkn_registry`。
  - `RuntimeContextBuilder.__init__` 增加可注入 `bkn_registry`。
  - 默认创建 `create_bkn_registry()`。
  - `build()` 填入 `bkn_registry`。
- `pyproject.toml`
  - 确认 package 列表包含 `bamboo.bkn`。

## 需要增加什么文件

- `bamboo/tools/buildin/bkn_retrieval.py`
- `tests/test_bkn_retrieval_tool.py`

## 测试

- 更新 `tests/test_tool_registry.py`
  - 断言存在 `bkn_retrieval`。
  - `summary().by_source["buildin"]` 总数加 1。
  - `summary().by_risk["read"]` 加 1。
- 工具无网络时返回 `count=0`。
- 工具在 fixture 网络下返回实体和关系。

## 验收标准

- Agent prompt 的 Available Tools 中出现 `bkn_retrieval`。
- 工具 schema 能被 LLM provider 正常序列化。
