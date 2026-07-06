# P2-17 Plugin Manifest Installer

## 当前状态

未完成。

当前 Bamboo 支持内置工具、MCP、skills、commands、workflows，但还没有统一 plugin manifest/installer。原计划里把 plugin manifest/installer 放在高级开发体验阶段。

## 目标

定义一个可安装的 Bamboo plugin 包格式，用于组合发布 skills、commands、workflows、MCP 配置片段和可选工具。

## 建议结构

```text
plugin-name/
  bamboo-plugin.yaml
  skills/
  commands/
  workflows/
  mcp.yaml
```

## 需要新增的文件

- `bamboo/plugins/models.py`
- `bamboo/plugins/installer.py`
- `bamboo/plugins/registry.py`
- `tests/test_plugin_installer.py`

## 需要修改的文件

- `bamboo/run.py`
  - 增加 `bamboo plugin install/list/remove`。
- `bamboo/userspace/userspace.py`
  - 增加 plugins 目录。
- `bamboo/skills/guard.py`
  - 复用安全扫描能力。

## 验收标准

- plugin 安装前进入 quarantine 并扫描。
- manifest 能声明安装哪些 skills/commands/workflows。
- 安装记录写 lock/audit。
- 卸载 plugin 不删除用户后续手动修改过的文件，除非显式 force。
