# P2-06 Memory Update And Backfill Tools

## 排期信息

- 建议顺序：4
- 建议阶段：P1 - 核心用户能力
- 重要程度：高
- 优先级：P1
- 依赖关系：建议在 `P2-04 Prompt Section Object Model` 之后实施，便于验证 memory 更新后 prompt 注入是否生效。

## 功能定位

这是记忆系统从“可检索”升级到“可维护”的工具能力。当前已有 knowledge/source log 检索和 KnowledgeSubagent 后处理，但用户还不能稳定通过对话读取、搜索、修正、忘记或回填知识。该需求完成后，chat/project/project-specific 记忆可以被工具安全更新，并保留来源线索。

## 当前状态

部分完成。

当前已有：

- `MemoryManager`
- chat/project/global/project-specific knowledge 模板
- `memory_retrieve` 工具，支持 `knowledge/source_log/all`
- `KnowledgeSubagent` 后处理
- source log 检索

roadmap 中还没有完成的部分：

- `memory_read`
- `memory_search`
- `memory_update`
- `memory_backfill_from_logs`
- source log 命中高价值信息后自动 backfill 到 md knowledge 的完整链路。

## 目标

补齐记忆的读、查、改、回填能力，让用户可以通过对话修正知识，Agent 可以从源日志补回稳定知识。

## 需要新增的文件

- `bamboo/tools/buildin/memory.py`
  - 单文件放置 memory 管理工具，避免散落多个工具文件。
  - 工具名建议：
    - `memory_read`
    - `memory_search`
    - `memory_update`
    - `memory_backfill`

## 需要修改的文件

- `bamboo/tools/buildin/__init__.py`
  - 注册新增 memory tools。
- `bamboo/memory/manager.py`
  - 增加安全读取指定 knowledge 文件。
  - 增加原子更新 knowledge 文件。
  - 增加从 source log 生成候选 patch 的接口。
- `bamboo/memory/knowledge_subagent.py`
  - 支持 backfill 模式。
- `bamboo/prompts/*`
  - 明确用户要求“记住/忘记/修正记忆”时调用 memory 工具。
- `tests/test_memory_tools.py`
  - 覆盖 chat/project scope 隔离。
  - 覆盖 update 后下一轮 prompt 生效。
  - 覆盖 backfill 不把大段工具输出写入 md。

## 权限建议

- `memory_read` / `memory_search`：`read`
- `memory_update` / `memory_backfill`：`write`

## 验收标准

- 用户说“记住/忘记/修正”时可以通过工具更新 md knowledge。
- project 模式只更新当前项目 knowledge，不污染其他项目。
- chat 模式只更新 chat knowledge。
- backfill 结果保留 `source: session_id/task_id` 线索。
