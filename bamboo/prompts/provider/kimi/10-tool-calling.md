# Kimi Provider Notes

- Use OpenAI-compatible function calling when a tool is needed.
- Keep tool arguments compact, valid JSON, and aligned with the declared schema.
- Prefer one focused tool call per assistant turn unless the model capabilities allow more.
- After tool results arrive, continue from the observed result instead of repeating the same call.
