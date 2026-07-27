# Aliyun Provider Notes

- Aliyun text models use the OpenAI-compatible chat completions protocol.
- Use tool calls normally when the selected model declares `capabilities.tool_calling: true`.
- Use the dedicated media tools for image generation, image editing, and video generation instead of asking the text model to produce binary media directly.
