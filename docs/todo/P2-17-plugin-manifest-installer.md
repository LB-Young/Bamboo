# P2-17 Plugin Manifest Installer

## 一句话说明

给 Bamboo 增加一个统一的 plugin 包格式，让别人可以一次性分发 skill、command、workflow、MCP 配置，而不是让用户手动复制很多文件。

## 为什么要做

现在 Bamboo 已经有很多扩展点：

- skills
- commands
- workflows
- MCP 配置
- 将来可能还有工具、prompt 片段、provider preset

但这些能力现在是分散安装的。用户如果想安装一个完整扩展包，可能需要：

1. 复制 skill 目录。
2. 复制 command md。
3. 复制 workflow 目录。
4. 手动合并 MCP 配置。
5. 自己判断这些文件是否安全。

Plugin installer 的目标是把这些操作变成一个受控安装流程：

```bash
bamboo plugin install ./my-plugin
bamboo plugin list
bamboo plugin remove my-plugin
```

## 做完以后是什么效果

一个 plugin 可以长这样：

```text
my-plugin/
  bamboo-plugin.yaml
  skills/
    pr-review/SKILL.md
  commands/
    pr-summary.md
  workflows/
    release-check/
      WORKFLOW.md
      scripts/check.sh
  mcp.yaml
```

manifest 示例：

```yaml
name: github-helper
version: 0.1.0
description: GitHub PR review helpers
publisher: local

skills:
  - path: skills/pr-review

commands:
  - path: commands/pr-summary.md

workflows:
  - path: workflows/release-check

mcp:
  path: mcp.yaml
```

用户安装后，Bamboo 会把这些能力复制到用户空间，并记录这个 plugin 安装了哪些文件。

## 为什么不能只用 skill installer

Skill installer 只解决 skill 的安装。

Plugin installer 要解决的是“组合包”：

- 一个 plugin 可以同时带 skill + command + workflow + MCP。
- 安装前要整体扫描。
- 卸载时要知道哪些文件属于这个 plugin。
- 需要避免覆盖用户手动修改过的文件。

## 安全原则

Plugin 是分发机制，风险比单个 skill 更大，所以必须保守：

- 安装前先进入 quarantine。
- 对所有脚本、workflow、command、skill 做扫描。
- MCP 配置不能静默启用危险 server。
- 写入用户空间前要记录 manifest 和文件 hash。
- 卸载时如果文件被用户改过，不默认删除。

## 不做什么

- 不做远程 marketplace。
- 不自动从互联网下载 plugin。
- 不绕过现有 Skill Guard、PermissionPolicy、MCP lifecycle。
- 不允许 plugin 安装后自动执行脚本。

## 建议命令

```bash
bamboo plugin install ./my-plugin
bamboo plugin list
bamboo plugin show github-helper
bamboo plugin remove github-helper
bamboo plugin validate ./my-plugin
```

## manifest 需要包含什么

建议 `bamboo-plugin.yaml` 字段：

- `name`
- `version`
- `description`
- `publisher`
- `skills`
- `commands`
- `workflows`
- `mcp`
- `permissions`：声明该 plugin 可能需要的能力
- `compatibility`：Bamboo 最低版本

## 安装流程

1. 读取 `bamboo-plugin.yaml`。
2. 校验 manifest 格式。
3. 拷贝 plugin 到 quarantine。
4. 扫描：
   - skill frontmatter
   - command md
   - workflow md 和 scripts
   - mcp.yaml
5. 如果扫描有高风险项，默认拒绝，除非用户显式 `--force`。
6. 拷贝文件到用户空间：
   - `~/.bamboo/skills`
   - `~/.bamboo/commands`
   - `~/.bamboo/workflows`
   - `~/.bamboo/configs/mcp.d` 或类似目录
7. 写安装 lock：
   - plugin 名称
   - 版本
   - 安装时间
   - 每个文件的目标路径和 hash
8. 写 audit log。

## 卸载流程

1. 读取 plugin lock。
2. 对比当前文件 hash。
3. 未修改的文件可以删除。
4. 被用户修改过的文件默认保留，并提示。
5. `--force` 才删除被修改文件。

## 需要新增的文件

- `bamboo/plugins/__init__.py`
- `bamboo/plugins/models.py`
- `bamboo/plugins/manifest.py`
- `bamboo/plugins/installer.py`
- `bamboo/plugins/registry.py`
- `tests/test_plugin_installer.py`

## 需要修改的文件

- `bamboo/run.py`
  - 增加 `bamboo plugin install/list/show/remove/validate`
- `bamboo/userspace/userspace.py`
  - 增加 plugins/quarantine/locks 目录。
- `bamboo/skills/guard.py`
  - 复用或抽取扫描能力给 plugin installer。
- `pyproject.toml`
  - 加入 `bamboo.plugins` 包。

## 验收标准

- 可以安装一个只包含 skill 的 plugin。
- 可以安装一个包含 skill + command + workflow 的 plugin。
- 安装前会生成扫描结果。
- 安装记录写入 lock，包含文件 hash。
- `plugin list/show` 能展示安装来源和文件列表。
- `plugin remove` 默认不删除用户修改过的文件。
- manifest 缺字段、路径越界、重复文件名都会被拒绝。

