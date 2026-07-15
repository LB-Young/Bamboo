# Feature 2.4：`bkn_query` 和 `bkn_load_context` 工具

## 目标

拆分骨架查询和上下文装载工具，降低单次调用成本和权限复杂度。

## 需要干什么

- 新增 `bkn_query`，只查骨架，不拉数据层。
- 新增 `bkn_load_context`，调用 Context Loader 返回 `BknSnapshot`。
- 保留 `bkn_retrieval` 作为兼容/高级入口，或让其内部调用这两个能力。

## 为什么

- 图谱查询和上下文装载是不同成本的操作。模型需要一个轻量工具先定位，再按需装载属性。
- 拆分后更容易做权限、审计和错误恢复。

## 需要改什么文件

- `bamboo/tools/buildin/__init__.py`
  - 注册新工具。
- `bamboo/runtime/runtime_context.py`
  - 确认新工具能拿到 `bkn_registry`。
- `tests/test_tool_registry.py`
  - 更新工具数量和风险统计。

## 需要增加什么文件

- `bamboo/tools/buildin/bkn_query.py`
- `bamboo/tools/buildin/bkn_load_context.py`
- `tests/test_bkn_query_tool.py`
- `tests/test_bkn_load_context_tool.py`

## 测试

- `bkn_query` 不读取数据层。
- `bkn_load_context` 会读取数据层并返回 snapshot。
- 两个工具均为 read risk。

## 验收标准

- Agent 可以先 query 再 load context，完成一个业务对象问题回答。
