# P2-04 Prompt Section Object Model

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
