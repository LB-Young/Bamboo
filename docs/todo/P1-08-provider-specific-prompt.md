# P1-08 Provider Specific Prompt

## 目标

根据模型平台和能力加载不同 prompt section，提升 tool calling 和输出稳定性。

## 参考

- OpenCode：不同模型族加载不同 provider prompt。
- Claude Code Source：custom/agent/append prompt 有优先级。

## 配置建议

```yaml
models:
  deepseek-chat:
    provider: deepseek
    prompt_profile: deepseek
    capabilities:
      tool_calling: true
      json_schema: false
      vision: false
      max_parallel_tools: 1
```

## 目录建议

```text
~/.bamboo/prompts/provider/
  deepseek/*.md
  gpt/*.md
  claude/*.md
  minimax/*.md
```

## 实现步骤

1. `ModelConfig` 增加 capabilities 和 prompt_profile。
2. Prompt builder 根据 model config 加载 provider section。
3. OpenAI-compatible provider 加 function calling 提示。
4. Claude provider 加 tool_use/tool_result 兼容提示。
5. 不支持 tool calling 的模型走文本协议 fallback。

## 验收标准

- 不同 provider 加载不同 prompt section。
- 修改 userspace provider prompt 后下一轮生效。
- capabilities 能影响工具调用策略。

## 非目标

- 不新增更多 provider。
