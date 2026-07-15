# Feature 3.1：`bkn_ingest` 草稿生成

## 目标

让用户能在会话中主动接入新平台，并生成 BKN 草稿和预览。

## 需要干什么

- 新增 `bkn_ingest`，接受 platform_id、manifest_draft、schema_doc、relation_doc、api_doc、openapi_spec、metric_definition 等输入。
- 输出到草稿区，不直接写正式区。
- 生成 `preview.md`，包含摘要和 mermaid 图。

## 为什么

- BKN 不应该从历史对话自动生成正式图谱。用户主动接入 + 草稿审核更可控。
- 草稿区能降低 agent 误写结构化知识的风险。

## 需要改什么文件

- `bamboo/tools/buildin/__init__.py`
  - 注册 `BknIngestTool`。
- `bamboo/bkn/models.py`
  - 增加 ingest draft 模型。

## 需要增加什么文件

- `bamboo/bkn/ingest.py`
- `bamboo/tools/buildin/bkn_ingest.py`
- `tests/test_bkn_ingest.py`
- `tests/test_bkn_ingest_tool.py`

## 测试

- ingest 只写 `*.draft.*` 和 `preview.md`。
- platform_id 已 active 时拒绝覆盖。
- 无效 schema 生成 draft 失败并带错误说明。

## 验收标准

- 用户给一段实体/关系说明后，能得到可阅读的 preview 和草稿文件。
