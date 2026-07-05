# DeepSeek Provider Notes

- Use the provided function tools exactly as declared.
- Keep tool arguments compact and valid JSON.
- Prefer one tool call per assistant turn unless the model capabilities allow more.
- After tool results arrive, continue from the observed result instead of repeating the same call.
