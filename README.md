# Bamboo

Bamboo is a Python agent runtime for local CLI, Web, desktop, and IM workflows. It turns a user request into a managed task, routes it through a configurable LLM, executes approved tools, and persists the full session trace for resume, replay, automation, and evaluation.

> Status: early-stage project. APIs, command names, and configuration files may still change.

## Features

- Multiple adapters: CLI, Web, Fancy Web, desktop App, Fancy desktop App, and WeChat
- Chat and project-scoped sessions with persisted traces
- Configurable LLM providers: Kimi, DeepSeek, GPT, Claude, MiniMax, Mimo, Ollama, and vLLM
- Tool execution with permission policy, audit events, sandboxing, and approval hooks
- Persistent session memory, replay, eval export, and trace inspection
- Skills, workflows, plugins, MCP tools, cron jobs, and BKN knowledge retrieval
- Fancy desktop UI with model switching, Git-backed Diff view, context usage meter, light/dark themes, and stateful context spirit

## Requirements

- Python 3.11+
- A configured model provider API key, unless you use a local provider such as Ollama or vLLM

## Installation

```bash
git clone https://github.com/LB-Young/Bamboo.git
cd Bamboo
pip install -e .
bamboo init
```

If you want to use browser automation, install the Playwright Chromium runtime manually after installing Bamboo:

```bash
python -m playwright install chromium
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

Bamboo currently defaults to `kimi-k3`. After `bamboo init`, configure the Kimi API key in `~/.bamboo/configs/models.yaml`:

```yaml
default_model: kimi-k3

models:
  kimi-k3:
    provider: kimi
    model: kimi-k3
    model_type: vision
    prompt_profile: kimi
    api_key: "${MOONSHOT_API_KEY}"
    base_url: https://api.moonshot.cn/v1
    timeout: 60
    context_window: 1000000
    max_tokens: 4096
    extra_body:
      reasoning_effort: max
    capabilities:
      tool_calling: true
      json_schema: false
      vision: true
      max_parallel_tools: 1
```

Confirm the main agent uses that model in `~/.bamboo/configs/bamboo_main_agent.yaml`:

```yaml
model: kimi-k3
tool_call_timeout_seconds: 120
```

`tool_call_timeout_seconds` is the global timeout for one tool call. When a tool exceeds it, Bamboo records a tool error and lets the agent continue with another approach.

Run Bamboo:

```bash
export MOONSHOT_API_KEY="your-kimi-api-key"
bamboo app-fancy
```

`app-fancy` is the recommended default interface. It starts a native desktop workspace with chat, model switching, Diff, logs, context usage, and theme controls.

Run a one-shot task:

```bash
bamboo run "检查这个项目最近有哪些改动"
```

Start a project-scoped session:

```bash
bamboo app-fancy --session-mode project --project /path/to/project
```

Ask about an image from the CLI:

```bash
bamboo main --msg "这张图里有什么？" --image /path/to/image.png
```

Or start the Web UI:

```bash
bamboo web
```

The Web UI opens at:

```text
http://127.0.0.1:8899
```

Other interactive frontends:

```bash
bamboo main
bamboo web-fancy
bamboo app
```

The `app-fancy` interface includes:

- a `Context` panel with calm / warning / critical context-spirit images
- a `Light` / `Dark` theme toggle in the top bar
- a model selector for new turns
- a Git-backed Diff panel

The Diff panel reads from Git working tree state. It shows tracked changes, staged changes, and untracked files visible to Git. Ignored files or files outside the selected project repository will not appear.

Start the WeChat personal-account adapter:

```bash
bamboo wechat
bamboo wechat --relogin
bamboo wechat --session-mode project --project /path/to/project
```

The WeChat adapter uses iLink QR login and stores the token in `~/.wxbot/token.json`. It currently supports text messages. Send `/new` or `/reset` in WeChat to start a new Bamboo session for that WeChat user.

## Other Models

Bamboo also supports `deepseek`, `gpt`, `claude`, `minimax`, `mimo`, `aliyun`, `openrouter`, `flux`, `generic_http`, `ollama`, and `vllm`. Register the model in `~/.bamboo/configs/models.yaml`, set chat models to `model_type: text` or `vision`, then set the selected registration name in `~/.bamboo/configs/bamboo_main_agent.yaml`.

Aliyun Bailian / DashScope text models can be used as the main Bamboo model through the OpenAI-compatible endpoint:

```yaml
models:
  aliyun-qwen-plus:
    provider: aliyun
    model: qwen-plus
    model_type: text
    prompt_profile: aliyun
    api_key: "${DASHSCOPE_API_KEY}"
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    timeout: 60
    context_window: 128000
    max_tokens: 4096
    capabilities:
      tool_calling: true
      json_schema: false
      vision: false
      max_parallel_tools: 1
```

Media generation models are registered in the same `models.yaml` with `model_type: image_generation`, `image_edit`, or `video_generation`. They are not shown in the app model selector; Bamboo exposes them through generic tools named `text_to_image`, `image_edit`, and `text_to_video`. The model entry declares its calling protocol in `extra_body.protocol`, while `~/.bamboo/configs/tools.yaml` controls which registered model each tool uses:

```yaml
media_generation:
  text_to_image_model: openrouter-gpt-5-image-mini
  image_edit_model: aliyun-wanx-image-edit
  text_to_video_model: aliyun-wanx-t2v
  output_dir: ~/.bamboo/workspace/media-generation
  poll_interval_seconds: 2
  timeout_seconds: 600
```

Example OpenRouter image model registration:

```yaml
models:
  openrouter-gpt-5-image-mini:
    provider: openrouter
    model: openai/gpt-5-image-mini
    model_type: image_generation
    prompt_profile: openrouter
    api_key: "${OPENROUTER_API_KEY}"
    base_url: https://openrouter.ai/api/v1
    timeout: 180
    context_window: 4096
    max_tokens: 1024
    extra_body:
      protocol: openrouter_images
      endpoint: /images
      parameters:
        n: 1
```

Example vLLM OpenAI-compatible server with tool calling enabled:

```bash
vllm serve Qwen/Qwen2.5-32B-Instruct \
  --served-model-name qwen2.5-32b \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key EMPTY \
  --tensor-parallel-size 2 \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.90 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes
```

Then register it in `~/.bamboo/configs/models.yaml`:

```yaml
models:
  qwen2.5-32b:
    provider: vllm
    model: qwen2.5-32b
    model_type: text
    prompt_profile: vllm
    api_key: "EMPTY"
    base_url: http://localhost:8000/v1
    timeout: 120
    context_window: 16384
    max_tokens: 4096
    capabilities:
      tool_calling: true
      json_schema: false
      vision: false
      max_parallel_tools: 1
```

For a multimodal vLLM model, add the model-specific vision options such as `--limit-mm-per-prompt image=4`, set `model_type: vision`, and set `capabilities.vision: true`. Tool calling still requires the parser/template supported by that specific model.

Example Gemma4 vLLM server with tool calling and reasoning parsing enabled:

```bash
CUDA_VISIBLE_DEVICES=0,1 vllm serve gemma-4-31B-it \
  --tensor-parallel-size 2 \
  --trust-remote-code \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name gemma-4-31b \
  --gpu-memory-utilization 0.8 \
  --enable-auto-tool-choice \
  --tool-call-parser gemma4 \
  --reasoning-parser gemma4 \
  --chat-template gemma-4-31B-it/chat_template.jinja
```

Register the served Gemma4 model in `~/.bamboo/configs/models.yaml`:

```yaml
models:
  gemma-4-31b:
    provider: vllm
    model: gemma-4-31b
    model_type: text
    prompt_profile: vllm
    api_key: "EMPTY"
    base_url: http://localhost:8000/v1
    timeout: 120
    context_window: 131072
    max_tokens: 4096
    capabilities:
      tool_calling: true
      json_schema: false
      vision: false
      reasoning: true
      max_parallel_tools: 1
```

For the full model configuration and command reference, run:

```bash
bamboo docs
```

Additional repository docs:

- [Adapter guide](docs/adapters.md)
- [BKN usage](docs/bkn.md)
- [BKN design](docs/bkn-design.md)
- [BKN graph design](docs/bkn-graph-design.md)


## License

This project is available for personal learning, academic study, research, and
other non-commercial educational purposes only. Commercial use requires prior
written permission. For commercial licensing, contact `lby15356@gmail.com`.

See [LICENSE](LICENSE) for the full terms.
