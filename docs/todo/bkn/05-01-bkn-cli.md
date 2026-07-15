# Feature 5.1：BKN CLI

## 目标

提供不用启动 agent 也能管理和调试 BKN 的 CLI。

## 需要干什么

- 增加命令：
  - `bamboo bkn list`
  - `bamboo bkn validate [network|platform_id]`
  - `bamboo bkn index [network|platform_id]`
  - `bamboo bkn search "query"`
  - `bamboo bkn export`

## 为什么

- 用户需要不经过 agent 就能排错 BKN 包。
- CLI 是测试和文档最稳定的手工验收入口。

## 需要改什么文件

- `bamboo/run.py`
  - 注册 bkn Typer 子命令。
- `bamboo/adapters/cli/main.py` 或现有 CLI 命令组织文件
  - 如果当前命令结构要求，需要接入。

## 需要增加什么文件

- `bamboo/bkn/cli.py`
- `tests/test_bkn_cli.py`

## 测试

- list 能输出 fixture 网络。
- validate 对坏 fixture 返回非零。
- search 能输出命中结果。

## 验收标准

- 不启动 agent 也能调试 BKN。
