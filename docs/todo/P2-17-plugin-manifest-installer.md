# P2-17 Plugin Manifest Installer

## 排期信息

- 建议顺序：8
- 建议阶段：P3 - 生态和分发
- 重要程度：中低
- 优先级：P3
- 依赖关系：依赖现有 skills、commands、workflows、MCP 配置和 Skill Guard 扫描能力。

## 功能定位

这是 Bamboo 扩展能力的打包、安装和卸载机制。当前各类扩展能力已经分散存在，但没有统一 plugin manifest 和 installer。该需求完成后，可以用一个 plugin 包组合发布 skills、commands、workflows、MCP 配置片段，并通过 quarantine、扫描、lock/audit 控制安装风险。

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
