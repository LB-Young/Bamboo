# Feature 2.3：Context Loader 和 Snapshot

## 目标

实现 `BknLoader`，把 focus nodes 装配成模型可读的 `BknSnapshot`。

## 需要干什么

- 给定 focus nodes，装配 skeleton、动态属性、operator outputs、available actions、open hypotheses。
- 输出 `BknSnapshot`，供工具或未来 prompt section 使用。

## 为什么

- 检索只回答“命中了什么”，loader 负责把可推理上下文装配成模型能读的结构。
- 这是 KWeaver “意图识别 -> 拓扑定位 -> 上下文装载 -> 决策行动”中的关键层。

## 需要改什么文件

- `bamboo/bkn/models.py`
  - 增加 `BknSnapshot`、`BknAttrFetch`。
- `bamboo/bkn/retrieval.py`
  - 检索命中后可调用 loader 装配结果。

## 需要增加什么文件

- `bamboo/bkn/loader.py`
  - 如果 Milestone 1 已有 loader，此处扩展为 runtime loader。
- `bamboo/bkn/attrs_store.py`
  - `BknAttrsStore`
  - `BknDataSourceAdapter`
  - local file/sqlite adapters
- `bamboo/bkn/prompt_render.py`
  - `render_bkn_snapshot(...)`
- `tests/test_bkn_loader_snapshot.py`

## 测试

- attr source 失败时 snapshot 包含 `attrs_unavailable`，整体不失败。
- action 被 manifest allowlist 过滤。
- operator 默认只返回定义，不执行有副作用代码。

## 验收标准

- snapshot 输出稳定，适合直接放进 tool result 或 prompt section。
