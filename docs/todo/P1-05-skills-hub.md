# P1-05 Skills Hub

## 目标

实现技能注册、摘要注入和按需加载，让 Agent 能根据任务使用专门工作流。

## 参考

- OpenCode：system prompt 注入 skill 列表，通过 skill tool 按需加载完整内容。
- Auton：SkillRegistry 注入 skill 摘要和部分完整 SKILL.md。
- Claude Code Source：skill discovery prefetch。

## 目录结构

```text
~/.bamboo/skills/{skill_name}/
  SKILL.md
  config.yaml
  scripts/
```

## 实现步骤

1. 新增 `SkillRegistry`，扫描 buildin 和 userspace。
2. 读取 `SKILL.md` frontmatter/name/description。
3. Prompt 中只注入 skill 摘要列表。
4. 新增 `skill_load` tool，按名称加载完整 SKILL.md 到 session。
5. 新增轻量 `SkillSelector`，根据 query 匹配候选 skill。
6. 记录 skill 使用事件：selected/loaded/failed。

## 验收标准

- 新增 skill 文件后下一轮可见。
- Agent 能看到 skill 摘要。
- 调用 `skill_load` 后完整 skill 指令进入上下文。
- 不把所有 skill 全文塞进 system prompt。

## 非目标

- 不实现 skill 自动生成。
- 不实现 skill 性能优化。
