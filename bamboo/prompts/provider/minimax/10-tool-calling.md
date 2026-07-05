# MiniMax Provider Notes

- Use OpenAI-compatible function calling when a tool is needed.
- Keep tool arguments valid JSON and aligned with the declared schema.
- Prefer one tool call per assistant turn unless the model capabilities allow more.
- If a tool is unavailable, explain the limitation using visible context.
