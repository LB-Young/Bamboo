# Feature 3.2：`bkn_ingest_submit` 显式提交

## 目标

让用户显式批准草稿进入正式 BKN，提交过程必须原子化。

## 需要干什么

- 新增提交流程：`approve=True` 时原子提交 draft 到正式区。
- 支持用户 edits 覆盖草稿字段。
- 提交成功后发布 EventBus 事件。

## 为什么

- 正式 BKN 是后续检索和行动判断的依据，必须有显式确认门。
- 原子提交避免半写入导致 registry 读到坏状态。

## 需要改什么文件

- `bamboo/bkn/ingest.py`
  - 增加 submit 逻辑。
- `bamboo/tools/buildin/__init__.py`
  - 注册 submit 工具，或让 `bkn_ingest` 支持 `mode=submit`。

## 需要增加什么文件

- `bamboo/tools/buildin/bkn_ingest_submit.py` 或合并到 `bkn_ingest.py`
- `tests/test_bkn_ingest_submit.py`

## 测试

- `approve=False` 不提交。
- manifest/schema platform_id 不一致拒绝。
- 提交成功后 draft 清理。
- EventBus 收到 `bkn.platform.activated`。

## 验收标准

- 新平台从草稿进入 active 后，`bkn_query` 能查到。
