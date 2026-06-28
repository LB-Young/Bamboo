# P1-06 Model Fallback And Auxiliary Router

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

1. LLM 错误增加分类：rate_limit、auth、server_error、timeout、context_length、invalid_response。
2. 新增 `LLMRouter` 或扩展 `LLMFactory`，支持 main/fallback/auxiliary。
3. `_think` 捕获可 fallback 错误并切换一次。
4. session metadata 记录 `fallback_used=true`。
5. compaction、memory、skills_hub 通过 auxiliary router 获取模型。
6. fallback 失败后清晰报错，不无限切换。

## 验收标准

- 429/5xx/timeout 可触发 fallback。
- auth 错误不盲目重试。
- fallback 每个 session 最多一次。
- compaction 模型可单独配置。

## 非目标

- 不实现多级 fallback 链。
- 不实现自动模型测速。
