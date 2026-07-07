# MiMo Provider Notes

- MiMo uses an OpenAI-compatible Chat Completions interface.
- Use normal function tool calling when the active model declares tool support.
- Keep tool arguments strict JSON and avoid relying on provider-specific hidden state.
