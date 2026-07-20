# Bamboo

Bamboo is a Python agent runtime for local CLI and Web workflows. It turns a user request into a managed task, routes it through a configurable LLM, executes approved tools, and persists the full session trace for resume, replay, automation, and evaluation.

> Status: early-stage project. APIs, command names, and configuration files may still change.

## Features

- CLI and Web agent experience
- Chat and project-scoped sessions
- Configurable LLM providers
- Tool execution with permission approval
- Persistent session memory and replay
- Skills, workflows, plugins, MCP, cron, and eval support

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
```

Run Bamboo:

```bash
export MOONSHOT_API_KEY="your-kimi-api-key"
bamboo main
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

## Other Models

Bamboo also supports `deepseek`, `gpt`, `claude`, `minimax`, `mimo`, `ollama`, and `vllm`. Register the model in `~/.bamboo/configs/models.yaml`, set `model_type` to `text` or `vision`, then set the selected registration name in `~/.bamboo/configs/bamboo_main_agent.yaml`.

For the full model configuration and command reference, run:

```bash
bamboo docs
```


## License

This project is available for personal learning, academic study, research, and
other non-commercial educational purposes only. Commercial use requires prior
written permission. For commercial licensing, contact `lby15356@gmail.com`.

See [LICENSE](LICENSE) for the full terms.
