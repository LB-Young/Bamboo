# Feature 1.3：BKNRegistry 和轻量索引 Store

## 目标

实现 BKN 网络扫描、启用过滤、轻量索引和运行时状态存储。

## 需要干什么

- 实现 `BKNRegistry`，扫描用户 BKN 目录，加载启用的网络。
- 实现 `BKNStore`，保存轻量索引、state 和 audit。
- 第一版索引使用关键词倒排和邻接表，不引入向量库或图数据库。

## 为什么

- 工具调用时不能每次从零递归读完整目录。
- registry 是后续 `bkn_retrieval`、CLI、Web 管理和 subagent 的共同入口。

## 需要改什么文件

- `bamboo/userspace/userspace.py`
  - 复用 `get_user_bkn_dir()`、`get_bkn_storage_dir()`。

## 需要增加什么文件

- `bamboo/bkn/registry.py`
  - `BKNRegistry.refresh()`
  - `BKNRegistry.list()`
  - `BKNRegistry.get(name)`
  - `BKNRegistry.search(...)`
  - `create_bkn_registry(...)`
- `bamboo/bkn/store.py`
  - `indexes/{network}.json`
  - `state.json`
  - `audit.jsonl`
- `tests/test_bkn_registry.py`
- `tests/test_bkn_store.py`

## 测试

- 启用网络会被扫描。
- `enabled: false` 网络不会进入默认列表。
- 一个网络解析失败不影响其他网络。
- 索引输出稳定，便于 debug。

## 验收标准

- registry 可以列出 fixture BKN。
- store 可以生成索引文件，并能被重复刷新覆盖。
