# P0-03 Tool Result Budget

## 当前状态

未完成。

当前 `AgentRuntime._execute_tool_call` 会把 tool result 直接写入 session。`ContextCompactor` 只能处理已有上下文整体预算，不能阻止单个超大 `read/grep/bash/web_fetch` 输出进入模型上下文。

## 目标

限制工具结果写入模型上下文的体积，防止单次工具输出撑爆上下文；UI 和审计仍应尽量保留完整或可追踪信息。

## 新增文件

- `bamboo/runtime/tool_result_budget.py`
- `tests/test_tool_result_budget.py`

## 修改文件

- `bamboo/runtime/agent_runtime.py`
  - 在 `_execute_tool_call` 得到工具结果后调用 budgeter。
  - 写入 session 的 tool result 使用截断版。
  - 发出的 `ToolResultEvent` 增加截断元信息。
- `bamboo/factory/message.py`
  - 确认 `Message.metadata` 可记录 `truncated/original_length/context_length`。
- `bamboo/helpers/constant.py`
  - `ToolResultEvent` 增加 `context_content`、`truncated`、`original_length`、`context_length` 字段，或至少增加 `metadata` 字段。

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
4. EventBus 事件保留 UI 可展示内容，并记录 `original_length`、`context_length` 和 `truncated`。
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
