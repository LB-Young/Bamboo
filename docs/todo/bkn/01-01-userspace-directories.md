# Feature 1.1：用户空间目录

## 目标

在 `~/.bamboo` 下创建 BKN 用户目录和运行时存储目录，并提供统一 helper。

## 需要干什么

- 创建 `~/.bamboo/bkn`，保存用户维护的 BKN 包。
- 创建 `~/.bamboo/storage/bkn`，保存索引、缓存、审计和状态。
- 增加目录定位 helper，供 registry、store、CLI、测试复用。

## 为什么

- BKN 是用户可维护的业务网络，不应该放进项目源码目录。
- 运行时生成的索引、缓存、审计数据需要和用户声明文件分离，避免 agent 改坏源定义。

## 需要改什么文件

- `bamboo/userspace/userspace.py`
  - `dirs` 增加 `bkn`、`storage/bkn`、`storage/bkn/indexes`、`storage/bkn/cache`。
  - 增加 `get_user_bkn_dir()`。
  - 增加 `get_bkn_storage_dir()`。

## 需要增加什么文件

- 可选：`bamboo/bkn/__init__.py`
- 可选：包内 BKN README 模板，用于初始化 `~/.bamboo/bkn/README.md`。

## 测试

- `tests/test_system_prompt.py` 或新增 `tests/test_bkn_userspace.py`
  - 断言 `ensure_userspace()` 后 BKN 目录存在。
  - 断言重复初始化不会覆盖用户文件。

## 验收标准

- 执行 `bamboo init` 后能看到 `~/.bamboo/bkn` 和 `~/.bamboo/storage/bkn`。
- 现有 userspace 初始化测试不回归。
