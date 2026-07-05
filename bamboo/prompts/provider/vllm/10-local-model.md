# vLLM Provider Notes

- Local OpenAI-compatible servers vary in tool calling support by model and launch options.
- If tool calling is disabled in model capabilities, answer only from visible context.
- Be explicit when the requested action requires a tool that is not available to this model.
- Keep responses short enough for the configured local context window.
