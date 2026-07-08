# Bamboo

Bamboo 是一个个人 Agent 助手框架，支持命令行任务执行、交互式对话、项目上下文模式、Web 对话入口、会话恢复、定时任务、Skills、Plugins 和 Eval 回放。

## 功能

- `bamboo main`：启动主 Agent 会话，支持交互式 CLI 和单轮任务。
- `bamboo run`：运行一次性任务，适合脚本或快速提问。
- `bamboo web`：启动 Web 对话入口并打开浏览器，支持 Chat 和 Project 模式。
- `bamboo docs`：启动 Web 服务并在浏览器中打开使用说明页。
- `bamboo replay`：查看已持久化 session，支持 `list`、`latest`、`-1`、`-2` 和 session id。
- `bamboo models discover`：发现 Ollama/vLLM 本地模型并写入模型配置。
- `bamboo skill` / `bamboo plugin`：管理能力扩展。
- `bamboo cron`：管理定时任务。
- `bamboo eval`：运行和导出 replay/live eval case。

## 安装

Bamboo 要求 Python 3.11+。

```bash
pip install -e .
```

开发环境安装：

```bash
pip install -e ".[dev]"
```

初始化用户目录：

```bash
bamboo init
```

初始化后会创建 `~/.bamboo`，常用配置文件包括：

```text
~/.bamboo/configs/models.yaml
~/.bamboo/configs/bamboo_main_agent.yaml
```

## 快速开始

默认主模型是 `deepseek-chat`。最短配置方式是在 `models.yaml` 中把 `deepseek-chat.api_key` 写成环境变量引用，然后设置对应环境变量。

```yaml
# ~/.bamboo/configs/models.yaml
default_model: deepseek-chat

models:
  deepseek-chat:
    provider: deepseek
    model: deepseek-chat
    prompt_profile: deepseek
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: https://api.deepseek.com/v1
    timeout: 60
    temperature: 0.2
    context_window: 128000
    max_tokens: 4096
    capabilities:
      tool_calling: true
      json_schema: false
      vision: false
      max_parallel_tools: 1
```

确认主 Agent 使用这个模型：

```yaml
# ~/.bamboo/configs/bamboo_main_agent.yaml
model: deepseek-chat
```

设置 API Key 后运行：

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
bamboo main --msg "帮我分析这个项目"
```

## 配置其他模型

Bamboo 的模型配置分两层：

- `models.yaml` 注册模型连接信息，包括 provider、真实模型 ID、API Key、base URL 和能力声明。
- `bamboo_main_agent.yaml` 选择主 Agent 使用哪个模型注册名。

当前支持的 provider：

- `deepseek`
- `minimax`
- `mimo`
- `gpt`
- `claude`
- `ollama`
- `vllm`

例如切换到 OpenAI 兼容 GPT：

```yaml
# ~/.bamboo/configs/models.yaml
default_model: gpt-default

models:
  gpt-default:
    provider: gpt
    model: gpt-4.1-mini
    prompt_profile: gpt
    api_key: "${OPENAI_API_KEY}"
    base_url: https://api.openai.com/v1
    timeout: 60
    temperature: 0.2
    context_window: 1047576
    max_tokens: 4096
    capabilities:
      tool_calling: true
      json_schema: true
      vision: false
      max_parallel_tools: 1
```

```yaml
# ~/.bamboo/configs/bamboo_main_agent.yaml
model: gpt-default
```

本地模型可以用发现命令生成配置：

```bash
bamboo models discover ollama
bamboo models discover ollama --write --set-default

bamboo models discover vllm --base-url http://localhost:8000/v1
bamboo models discover vllm --write --replace
```

`--write` 只会写入 `models.yaml`。如果要让主 Agent 使用发现到的模型，还需要把 `bamboo_main_agent.yaml` 的 `model` 改成对应注册名。

## 常用命令

启动交互式 CLI：

```bash
bamboo main
```

执行单轮任务：

```bash
bamboo main --msg "帮我总结这个仓库"
bamboo run "检查测试失败原因"
```

使用项目模式：

```bash
bamboo main --session-mode project --project /path/to/project
```

恢复会话：

```bash
bamboo main --resume SESSION_ID
bamboo run "继续刚才的分析" --resume SESSION_ID
```

启动 Web：

```bash
bamboo web
bamboo web --host 0.0.0.0 --port 9000
bamboo web --no-browser
```

默认地址：

```text
http://127.0.0.1:8899
```

`bamboo web` 默认会打开浏览器；服务器或脚本场景可用 `--no-browser` 只启动服务。

Web 模式下的使用说明页：

```text
http://127.0.0.1:8899/docs
```

启动文档服务并打开使用说明页：

```bash
bamboo docs
bamboo docs --port 9000
```

`bamboo docs` 会启动同一个 Web 应用并直接打开 `/docs`，终端进程会保持运行，按 `Ctrl+C` 停止服务。

如果 Web 服务已经在运行，只打开 URL：

```bash
bamboo docs --no-server
```

FastAPI OpenAPI UI 位于：

```text
http://127.0.0.1:8899/openapi-docs
```

## 查看历史会话

列出最近 sessions：

```bash
bamboo replay
```

列出全部可发现 sessions：

```bash
bamboo replay list
```

回放最近会话：

```bash
bamboo replay latest
bamboo replay last
bamboo replay -1
```

回放上上个会话：

```bash
bamboo replay -2
```

按 session id 回放：

```bash
bamboo replay SESSION_ID
bamboo replay SESSION_ID --json
```

## 扩展命令

Skills：

```bash
bamboo skill list
bamboo skill show skill-creator
bamboo skill create my-skill --description "自定义技能"
bamboo skill install local:/path/to/skill --trust local
```

Plugins：

```bash
bamboo plugin validate /path/to/plugin
bamboo plugin install /path/to/plugin
bamboo plugin list
bamboo plugin show plugin-name
bamboo plugin remove plugin-name
```

Cron：

```bash
bamboo cron list
bamboo cron add daily-review --schedule "0 9 * * *" --prompt "生成今日项目摘要"
bamboo cron start
bamboo cron tick
bamboo cron enable daily-review
bamboo cron disable daily-review
```

Eval：

```bash
bamboo eval run /path/to/case
bamboo eval export SESSION_ID /path/to/case --overwrite
```

## 开发

运行测试：

```bash
pytest
```

运行针对 Web docs 和 replay 的测试：

```bash
pytest tests/test_web_cli.py tests/test_docs_cli.py tests/test_web_docs.py tests/test_replay_cli.py
```
