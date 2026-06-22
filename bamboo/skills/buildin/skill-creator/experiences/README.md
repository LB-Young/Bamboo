# skill-creator 使用经验

本文档记录 Bamboo `skill-creator` 在实际使用中积累的经验和教训。使用此 skill 后，可追加新的经验条目，帮助后续任务复用成功路径并避免重复错误。

## 经验条目

### 2026-04-07: SKILL.md body 保持精简

- **场景**：将大量 API 文档直接写入 `SKILL.md` body，导致上下文膨胀。
- **教训**：详细参考文档应放在 `references/` 目录，只在 `SKILL.md` 主体中保留核心工作流、触发条件和关键示例。
- **标签**：#context #documentation

