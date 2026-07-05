# GPT Provider Notes

- Use OpenAI-compatible function calling when a tool is needed.
- Tool arguments must match the JSON schema and should not include extra commentary.
- Prefer one focused tool call per assistant turn unless the model capabilities allow more.
- When a tool result is sufficient, answer directly instead of calling another tool.
