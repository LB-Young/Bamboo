# P0-01 RuntimeContextBuilder

## 目标

把 Task 执行所需的运行依赖集中初始化，避免 `TaskRuntime` 和 `AgentRuntime` 随着能力增加持续变胖。

## 背景

当前 `TaskRuntime` 创建 `AgentRuntime` 时只处理模型名和压缩模型名，`AgentRuntime.__init__` 内部还会自行初始化 `ToolRegistry`、`AgentPromptBuilder`、`ContextCompactor` 等依赖。

后续 memory、skills、subagents、permission、trace、fallback 都会进入运行时。如果不先收敛初始化边界，后续会形成分散补丁。

## 参考

- Auton：`SessionFactory` 统一构建 userspace、LLM、tools、prompt、skills、subagents、processor。
- OpenCode：session prompt 处理前统一组合 env、skills、instructions、messages。

## 范围

新增：

- `bamboo/runtime/runtime_context.py`
- `RuntimeContext`
- `RuntimeContextBuilder`

调整：

- `TaskRuntime._create_agent`
- `AgentRuntime.__init__`

## 建议接口

```python
@dataclass(slots=True)
class RuntimeContext:
    task: Task
    session: Session
    event_bus: EventBus
    llm_factory: LLMFactory
    model_name: str
    compaction_model_name: str
    tool_registry: ToolRegistry
    prompt_builder: AgentPromptBuilder
    context_compactor: ContextCompactor
```

后续字段预留：

- `memory_manager`
- `skill_registry`
- `subagent_registry`
- `permission_policy`
- `trace_recorder`

## 实现步骤

1. 新增 `RuntimeContext` 数据类。
2. 新增 `RuntimeContextBuilder.build(task)`。
3. 把模型名解析从 `TaskRuntime._create_agent` 移到 builder。
4. 把 `ToolRegistry`、`AgentPromptBuilder`、`ContextCompactor` 的初始化移到 builder。
5. `AgentRuntime` 接收 `runtime_context`，不再自己创建这些依赖。
6. 保留测试注入能力，允许测试传 fake context 或 fake agent factory。

## 验收标准

- `AgentRuntime.__init__` 参数明显减少。
- CLI 和测试脚本仍能跑通。
- 后续新增 memory/skills/subagents 时只需要扩展 `RuntimeContextBuilder`。
- 原有 `tests/test_llms.py`、`tests/test_tool_registry.py` 通过。

## 非目标

- 不实现 memory、skills、subagents。
- 不改 Agent OTA 逻辑。
- 不改 LLM provider 实现。
