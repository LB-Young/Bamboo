# Feature 1.4：BKNRetrieval 检索流程

## 目标

实现 BKN 的只读检索流程，返回实体、关系、动态数据和 action 元数据。

## 需要干什么

- 实现关键词检索、实体 ID 精确匹配、class/name/tag/description 匹配。
- 根据 `max_hops` 扩展关系邻居。
- 第一版动态数据只支持 `static`、`file`、`json`、`csv`、`sqlite` 的只读读取。
- 渲染稳定 XML/Markdown，方便模型直接使用。

## 为什么

- 只读检索是 BKN 对 Bamboo 的最小价值闭环。
- 使用工具按需召回比每轮 prompt 注入整张网络更省上下文，也更符合当前 Bamboo 的工具目录机制。

## 需要改什么文件

- 无必须修改现有文件。

## 需要增加什么文件

- `bamboo/bkn/retrieval.py`
  - `retrieve_bkn(...)`
  - `render_bkn_results(...)`
  - `score_entity(...)`
  - `expand_relations(...)`
- `bamboo/bkn/source_readers.py`
  - `StaticSourceReader`
  - `FileSourceReader`
  - `JsonSourceReader`
  - `CsvSourceReader`
  - `SqliteSourceReader`
- `tests/test_bkn_retrieval.py`

## 测试

- 按标题召回实体。
- 按 tag 召回实体。
- `max_hops=0/1/2` 返回不同关系范围。
- `limit` 生效。
- 路径读取必须限制在 BKN 包目录或显式允许目录内，避免 `../` 越权。

## 验收标准

- 对 fixture 查询能返回实体、关系、action 元数据。
- 检索结果 metadata 包含 network、entity_id、score、source_path。
