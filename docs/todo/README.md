# Bamboo Agent 优化需求列表

本目录把 `docs/agent-optimization-roadmap.md` 拆成可逐个实现的需求文档。

建议按编号顺序推进。P0 是主循环稳定性和结构边界，P1 是效果提升，P2 是生态扩展。

## P0：主循环和运行时边界

1. `P0-01-runtime-context-builder.md`
2. `P0-02-prompt-section-pipeline.md`
3. `P0-03-tool-result-budget.md`
4. `P0-04-permission-policy.md`
5. `P0-05-session-store-and-trace.md`

## P1：效果和长期上下文

6. `P1-01-memory-source-log.md`
7. `P1-02-memory-knowledge-layer.md`
8. `P1-03-memory-query-retrieval.md`
9. `P1-04-knowledge-subagent.md`
10. `P1-05-skills-hub.md`
11. `P1-06-model-fallback-and-auxiliary-router.md`
12. `P1-07-reactive-compact.md`
13. `P1-08-provider-specific-prompt.md`
14. `P1-09-agent-trace-events.md`

## P2：扩展能力

15. `P2-01-subagent-runtime.md`
16. `P2-02-workflow-runner.md`
17. `P2-03-cron-heartbeat.md`

## 实施原则

- 每次只做一个需求，避免跨模块大面积重构。
- 每个需求完成后必须补测试和最小可运行验证。
- 新能力优先走现有主链路：`TaskFactory -> TaskRuntime -> AgentRuntime -> EventBus`。
- 用户空间内容必须优先可配置，包内内容作为默认模板。
