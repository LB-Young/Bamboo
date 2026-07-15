# Feature 2.2：SQLite Skeleton Store

## 目标

用 SQLite 保存节点、边和基础全文索引，并用 `events.jsonl` 审计拓扑变化。

## 需要干什么

- 用 SQLite 保存节点、边和基础全文索引。
- 拓扑变更写入 append-only `events.jsonl`。
- 节点只存稳定元信息，不保存热数据。

## 为什么

- YAML 图适合 MVP，不适合大量节点、邻居查询和版本审计。
- SQLite 是个人开发者可落地的本地依赖，不需要 Neo4j。

## 需要改什么文件

- `pyproject.toml`
  - 当前已有 `sqlite-minutils`，确认是否使用；如果不用，可直接用标准库 `sqlite3`。
- `bamboo/bkn/models.py`
  - 增加 `BknNode`、`BknEdge`、`BknNodeId`、`BknEdgeId`。
- `bamboo/bkn/retrieval.py`
  - 支持从 SQLite skeleton 查询。

## 需要增加什么文件

- `bamboo/bkn/store.py`
  - 如果 Milestone 1 已有 store，此处扩展为 skeleton store。
- `bamboo/bkn/graph.py`
  - `upsert_node`
  - `upsert_edge`
  - `get_node`
  - `find_nodes`
  - `neighborhood`
  - `path`
  - `search_by_text`
- `bamboo/bkn/events.py`
- `tests/test_bkn_graph_store.py`

## 测试

- upsert node 幂等。
- upsert edge 幂等。
- neighborhood depth 正确。
- `events.jsonl` 记录拓扑变更。

## 验收标准

- 1k 节点级别的 fixture 查询能在可接受时间内返回。
