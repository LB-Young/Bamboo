# P2-07 Auxiliary Model Router Expansion

## 排期信息

- 建议顺序：6
- 建议阶段：P2 - 质量工程和高级运行时
- 重要程度：中
- 优先级：P2
- 依赖关系：依赖现有 `LLMRouter`、main fallback、compaction route；建议等 memory/skills/web_extract 真实调用点更稳定后实施。

## 功能定位

这是辅助模型角色的路由扩展能力。当前 auxiliary route 主要服务 compaction，未来 memory、skills_hub、web_extract、vision 等任务可能需要独立模型和 fallback。该需求完成后，每个辅助任务可以单独配置模型链路，互不污染 fallback 状态。

## 当前状态

部分完成。

当前 `LLMRouter` 已支持 main route 和 compaction auxiliary route，也支持一次性 fallback。`AgentRuntime` 已接入主模型 fallback 和 reactive compact。

roadmap 中还没有完整实现的是多类 auxiliary task 的独立 provider chain，例如：

- skills_hub
- memory
- web_extract
- session_search
- memory_flush
- vision

## 目标

把辅助任务模型路由从“compaction 专用”扩展成通用能力，每类辅助任务可以声明自己的 model/fallback，并在失败时独立降级。

## 需要修改的文件

- `bamboo/configs/bamboo_main_agent.yaml`
  - 增加 `auxiliary_models` 配置段。
- `bamboo/llms/router.py`
  - 增加按 role 获取 auxiliary route 的稳定 API。
  - 每个 auxiliary route 独立记录 fallback 状态。
- `bamboo/runtime/runtime_context.py`
  - 构建常用 auxiliary routes。
  - 暴露给 KnowledgeSubagent、SkillHub、未来 web extract。
- `bamboo/memory/knowledge_subagent.py`
  - 使用 memory/knowledge 专用 auxiliary route。
- `bamboo/skills/hub.py`
  - 如需要模型辅助匹配，使用 skills_hub route。
- `tests/test_auxiliary_router.py`
  - 覆盖不同 auxiliary role 的 fallback 互不影响。

## 验收标准

- main fallback 不影响 compaction/memory/skills_hub 的 fallback 状态。
- auxiliary 模型不可用时有清晰降级路径。
- 配置缺失时默认复用 main model，不阻断任务。
