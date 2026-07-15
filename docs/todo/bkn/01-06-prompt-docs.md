# Feature 1.6：Prompt 使用规则和用户文档

## 目标

让模型知道什么时候该调用 BKN 工具，并让用户知道如何创建 BKN 包。

## 需要干什么

- 在 prompt 规则中说明：当用户询问平台数据、业务对象、内容资产、实体关系、跨平台状态时，优先调用 `bkn_retrieval`。
- 编写用户创建 BKN 包的文档。

## 为什么

- 只加工具不一定保证模型会用，需要在工具使用规则里给触发条件。
- 用户需要知道如何手写最小 BKN 包。

## 需要改什么文件

- `bamboo/prompts/project/30-tools-and-files.md`
- 可选：`bamboo/prompts/chat/30-tool-use.md`

## 需要增加什么文件

- `docs/bkn.md`
  - BKN 包结构。
  - personal-media 示例。
  - 常见错误。
- 可选：`docs/examples/bkn/personal-media/...`

## 测试

- 如果 `tests/test_system_prompt.py` 对 prompt 内容有断言，需要同步更新。

## 验收标准

- `bamboo docs` 或仓库文档能解释如何创建和查询 BKN。
- prompt 中有明确 `bkn_retrieval` 使用规则。
