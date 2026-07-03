# P1-07 Reactive Compact

## 当前状态

未完成。

当前已有请求前的 `ContextCompactor`，但模型请求失败后不会自动做 reactive compact 再重试。

## 目标

模型返回 context length 错误时，自动触发强制压缩并重试当前模型调用。

## 背景

当前 Bamboo 有请求前的 preemptive compact，但没有请求失败后的 reactive compact。

## 参考

- Claude Code Source：prompt-too-long withheld 后尝试 reactive compact。
- Hermes Agent：compression 失败可降级。
- OpenClaw：工具结果先治理，再进入上下文。

## 依赖

- `P0-03-tool-result-budget.md`
- `P1-06-model-fallback-and-auxiliary-router.md` 可后置，但错误分类应共用。

## 实现步骤

1. LLM provider 对 context length 错误抛出专门异常。
2. `_think` 捕获后调用 `ContextCompactor.compact(force=True)`。
3. compact 成功后重建 prompt 并重试一次。
4. compact 无收益时按低价值策略丢弃旧 tool result 或旧 assistant 输出。
5. `SessionCompactEvent` 增加 reason：preemptive/reactive/manual。

## 修改文件

- `bamboo/llms/base.py`
- `bamboo/llms/providers/openai_compatible.py`
- `bamboo/llms/providers/anthropic.py`
- `bamboo/runtime/agent_runtime.py`
- `bamboo/runtime/context_compactor.py`
- `bamboo/helpers/constant.py`

## 新增测试

- `tests/test_reactive_compact.py`

## 验收标准

- prompt too long 不直接失败任务。
- reactive compact 最多重试一次，避免死循环。
- compact 失败时有明确降级和错误记录。

## 非目标

- 不做复杂语义重要性排序。
