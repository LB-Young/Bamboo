# P2-04 Prompt Section Object Model

## 排期信息

- 建议顺序：4
- 建议阶段：P1 - 核心用户能力
- 重要程度：高
- 优先级：P1
- 依赖关系：依赖现有 `bamboo/prompts`、provider prompt、`AgentPromptBuilder` 和 session/task metadata。

## 功能定位

这是 prompt 构建链路的可调试对象模型。当前 prompt 已经支持基础分段和 provider 注入，但最终仍偏字符串拼接，难以追踪每段来源、优先级、hash 和缓存属性。该需求完成后，后续 memory、skills、provider prompt 的注入都能用统一 section 元数据调试和验证。

## 当前状态

部分完成。

项目已经有 `bamboo/prompts/{chat,project,shared}`、provider prompt、memory/tools/skills 注入，以及 `AgentPromptBuilder`。但 roadmap 中设计的显式 `PromptSection(name/priority/source/cacheable)` 对象模型还没有实现。

当前 `bamboo/prompts/system_prompt.py` 仍然主要返回字符串片段，调试时无法稳定看到每个 section 的名称、来源、优先级和是否可缓存。

## 目标

把 system prompt 构建升级为显式 section pipeline，让 prompt 的组成可调试、可排序、可追踪。

## 需要修改的文件

- `bamboo/prompts/system_prompt.py`
  - 新增 `PromptSection` dataclass。
  - `SystemPromptBuilder.build()` 先返回 section 列表，再 render 成最终字符串。
  - 每个 section 记录 `name/source/priority/cacheable/content`。
- `bamboo/runtime/prompt.py`
  - `AgentPromptBuilder` 接收 section 列表并渲染。
  - debug 场景可以输出 section metadata。
- `bamboo/runtime/task_runtime.py`
  - 创建任务后把最终 system prompt hash 写入 `task.metadata["system_prompt_hash"]`。
- `tests/test_system_prompt.py`
  - 覆盖 section 顺序、来源、hash、缺失文件跳过。

## 验收标准

- debug 输出可以看到每个 prompt section 的名称、来源和优先级。
- 修改 `~/.bamboo/prompts` 后下一轮任务立即生效。
- 缺失某个 prompt section 不会导致会话启动失败。
- `task.metadata` 中包含 system prompt hash。
