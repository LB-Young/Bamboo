# BKN 里程碑实施计划索引

本文档只保留 BKN 实施计划索引。每个 feature 的详细说明拆到 `docs/todo/bkn/` 下的独立文件中。

总体原则：

- 第一版优先只读，不执行业务 Action，不自动写图。
- 第一版优先本地文件数据源，不默认接 HTTP/API。
- BKN 不替代 Memory。Memory 保存自然语言长期知识，BKN 保存业务对象、关系、数据源、算子和行动元数据。
- 图谱只保存稳定拓扑和轻量元信息。状态、金额、阅读量、指标明细等热数据由数据源动态读取。
- 每个 feature 都要有测试和最小可手工验证路径。

## Milestone 1：只读 BKN MVP

- [Feature 1.1：用户空间目录](bkn/01-01-userspace-directories.md)
- [Feature 1.2：BKN 文件模型和 Loader](bkn/01-02-file-model-loader.md)
- [Feature 1.3：BKNRegistry 和轻量索引 Store](bkn/01-03-registry-store.md)
- [Feature 1.4：BKNRetrieval 检索流程](bkn/01-04-retrieval.md)
- [Feature 1.5：`bkn_retrieval` 内置工具](bkn/01-05-bkn-retrieval-tool.md)
- [Feature 1.6：Prompt 使用规则和用户文档](bkn/01-06-prompt-docs.md)

## Milestone 2：平台级 BKN 图谱骨架

- [Feature 2.1：Manifest 和平台命名空间](bkn/02-01-manifest-platform-scope.md)
- [Feature 2.2：SQLite Skeleton Store](bkn/02-02-sqlite-skeleton-store.md)
- [Feature 2.3：Context Loader 和 Snapshot](bkn/02-03-context-loader-snapshot.md)
- [Feature 2.4：`bkn_query` 和 `bkn_load_context` 工具](bkn/02-04-query-load-context-tools.md)

## Milestone 3：BKN 构建与审批闭环

- [Feature 3.1：`bkn_ingest` 草稿生成](bkn/03-01-bkn-ingest-draft.md)
- [Feature 3.2：`bkn_ingest_submit` 显式提交](bkn/03-02-bkn-ingest-submit.md)
- [Feature 3.3：`bkn_update_manifest` 和 `bkn_update_topology`](bkn/03-03-update-manifest-topology.md)

## Milestone 4：数据源、算子和行动闭环

- [Feature 4.1：HTTP/API 数据源适配器](bkn/04-01-http-api-source-adapter.md)
- [Feature 4.2：安全表达式算子](bkn/04-02-expression-operators.md)
- [Feature 4.3：BKN 私有 Action 脚本和工作流](bkn/04-03-action-mapping.md)

## Milestone 5：管理和可视化

- [Feature 5.1：BKN CLI](bkn/05-01-bkn-cli.md)
- [Feature 5.2：导出和可视化](bkn/05-02-export-visualization.md)

## 已删除的想法

- `bkn-architect` 子代理：现阶段过早。已有 `subagent_run` 和普通工具调用链路，BKN 设计流程可以先由主 agent + BKN 工具完成。
- Source Cache：现阶段会扩大安全面和一致性复杂度。HTTP/API 数据源先只读实时拉取；缓存等有真实性能压力后再加。
- 可选 Prompt Section 注入：和“工具按需召回”目标冲突，容易让普通编码任务背上 BKN 上下文成本。
- Memory 到 BKN 的桥接提议：自然语言 memory 置信度不够稳定，容易把低质量事实推向结构化图谱。后续可以作为人工命令或 ingest 输入，而不是独立后台链路。

## 建议实施顺序

1. 完成 Milestone 1 后再开始平台级图谱骨架。
2. 完成 `manifest + SQLite skeleton + bkn_query/bkn_load_context` 后，再考虑任何写工具。
3. 写工具必须接 permission 和 audit，不要绕过现有安全链路。
4. HTTP/API 和 Action 执行最后做，因为它们最容易引入网络、安全和权限问题。
5. 保持按需召回，不做默认 prompt 注入。

## 暂不做

- 不引入 Neo4j。
- 不引入向量数据库。
- 不让 `bkn_retrieval` 执行业务动作。
- 不让 KnowledgeSubagent 自动写正式图谱。
- 不把热数据、凭据、长文本 payload 存进 `graph.sqlite`。
- 不默认缓存平台 API 响应。
