# P1-06 Model Fallback And Auxiliary Router

## 当前状态

未完成。

当前 `LLMFactory` 已支持多 provider 和本地 `ollama/vllm`，但没有错误分类、fallback 策略和辅助模型路由。

## 目标

提升模型调用可靠性：主模型失败时支持一次 fallback，辅助任务使用独立模型路由。

## 参考

- Hermes Agent：primary fallback model 每 session 最多一次。
- Hermes Agent：compression、vision、session_search 等 auxiliary task 独立 provider chain。
- Claude Code Source：可恢复错误先尝试恢复，不直接暴露给用户。

## 配置建议

```yaml
agents:
  main:
    model: deepseek-chat
    fallback_model: gpt-default
  compaction:
    model: gpt-default
    fallback_model: deepseek-chat
  memory:
    model: deepseek-chat
  skills_hub:
    model: deepseek-chat
```

## 实现步骤

1. 在 `bamboo/llms/base.py` 增加结构化错误分类：rate_limit、auth、server_error、timeout、context_length、invalid_response。
2. 新增 `bamboo/llms/router.py`，支持 main/fallback/auxiliary。
3. `RuntimeContextBuilder` 使用 router 获取 main、compaction、memory 等客户端。
4. `AgentRuntime._think` 捕获可 fallback 错误并切换一次。
5. session metadata 记录 `fallback_used=true`、`fallback_from`、`fallback_to`。
6. compaction、memory、knowledge_subagent 通过 auxiliary router 获取模型。
7. fallback 失败后清晰报错，不无限切换。

## 修改文件

- `bamboo/llms/base.py`
- `bamboo/llms/factory.py`
- `bamboo/runtime/runtime_context.py`
- `bamboo/runtime/agent_runtime.py`
- `bamboo/configs/bamboo_main_agent.yaml`

## 新增文件

- `bamboo/llms/router.py`
- `tests/test_llm_router.py`

## 验收标准

- 429/5xx/timeout 可触发 fallback。
- auth 错误不盲目重试。
- fallback 每个 session 最多一次。
- compaction 模型可单独配置。

## 非目标

- 不实现多级 fallback 链。
- 不实现自动模型测速。
