# Feature 5.2：导出和可视化

## 目标

支持把 BKN 子图导出为 mermaid、dot 和 markdown，方便人工检查。

## 需要干什么

- 支持导出 mermaid、dot、markdown。
- 支持按 platform、node、depth 导出子图。

## 为什么

- BKN 是结构化网络，必须能被人检查。
- 可视化有助于用户审核 ingest 草稿和拓扑更新。

## 需要改什么文件

- `bamboo/bkn/graph.py`
  - 提供子图查询。

## 需要增加什么文件

- `bamboo/bkn/export.py`
- `bamboo/tools/buildin/bkn_export.py`
- `tests/test_bkn_export.py`

## 测试

- mermaid 输出稳定。
- dot 输出稳定。
- 空图输出合理提示。

## 验收标准

- 用户可以把任意平台的局部 BKN 导出成可读图。
