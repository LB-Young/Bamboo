# P0-03 Tool Result Budget

## 目标

限制工具结果写入模型上下文的体积，防止单次 `read/grep/bash` 输出撑爆上下文。

## 背景

当前工具执行结果会完整写入 session。上下文压缩只处理旧消息，对单个巨大的 tool result 没有保护。

## 参考

- OpenClaw：`tool-result-context-guard.ts` 对单个工具结果和工具结果总量做预算。
- Claude Code Source：对 prompt-too-long 这类可恢复错误延迟暴露并尝试恢复。

## 范围

新增：

- `bamboo/runtime/tool_result_budget.py`

调整：

- `AgentRuntime._execute_tool_call`
- `Message` 增加 metadata
- `ToolResultEvent` 区分 UI 输出和模型上下文输出

## 建议接口

```python
@dataclass(slots=True)
class ToolResultBudgetPolicy:
    max_single_result_tokens: int = 12000
    max_total_result_tokens: int = 30000
    preserve_head_chars: int = 6000
    preserve_tail_chars: int = 3000
    truncation_notice: str = "[truncated: tool output exceeded context budget]"
```

```python
class ToolResultBudgeter:
    def prepare_for_session(self, content: str, policy: ToolResultBudgetPolicy) -> BudgetedToolResult: ...
    def compact_old_tool_results(self, session: Session) -> None: ...
```

## 实现步骤

1. 实现简单 token 估算，复用 `HeuristicTokenCounter`。
2. 单个结果超限时保留头尾，中间插入 truncation notice。
3. 写入 session 的是截断版。
4. EventBus 事件可以保留完整输出，或至少记录 original_length 和 truncated。
5. 历史 tool result 总量超限时，替换最旧 tool result 内容为 compact placeholder。
6. 在测试中构造 100k 字符 tool result，确认 session 中被截断。

## 验收标准

- 大输出不会直接进入模型上下文。
- 模型能看到清晰截断提示。
- message metadata 记录 `truncated=true`、`original_length`。
- 现有工具调用测试仍通过。

## 非目标

- 不做语义摘要工具输出。
- 不改变工具本身执行逻辑。
