# Claude Provider Notes

- Use Anthropic tool_use blocks only when a tool is required.
- Treat tool_result content as observed data and do not invent missing fields.
- Prefer one tool use per assistant turn unless the model capabilities allow more.
- Keep the final response concise after the required tool results are available.
