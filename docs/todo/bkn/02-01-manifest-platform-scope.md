# Feature 2.1：Manifest 和平台命名空间

## 目标

从普通 network name 升级为 `platform_id` 一级命名空间，引入 manifest/schema 分层。

## 需要干什么

- 引入 `platform_id` 作为 BKN 一级命名空间。
- 每个平台目录包含 `manifest.yaml`、`manifest.md`、`schema.json`。
- manifest 包含状态、owner、domain、data_source_kind、cacheable、operator/action allowlist。

## 为什么

- 多平台场景下，权限、数据源、行动白名单必须和平台绑定，不能只靠 network name。
- manifest 是后续写入、action、cache 和跨平台边的安全入口。

## 需要改什么文件

- `bamboo/bkn/models.py`
  - 增加 `BknManifest`、`BknScope`。
- `bamboo/bkn/loader.py`
  - 支持从 `~/.bamboo/bkn/platforms/<platform_id>/manifest.yaml` 加载。
- `bamboo/bkn/validator.py`
  - 校验 `manifest.platform_id == schema.platform_id`。

## 需要增加什么文件

- `bamboo/bkn/manifest_io.py`
- `bamboo/bkn/scope.py`
- `tests/test_bkn_manifest.py`

## 测试

- manifest 必填字段缺失报错。
- paused/deprecated 平台不能被默认检索。
- schema platform_id 不一致时报错。

## 验收标准

- registry 能识别 platform BKN 包。
- 对旧 MVP BKN 包有兼容策略或迁移说明。
