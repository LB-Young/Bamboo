# Bamboo

Bamboo 是一个个人 Agent 助手框架，支持命令行任务执行、交互式对话、项目上下文模式和 Web 对话入口。

## 安装和配置

Bamboo 要求 Python 3.11+。

在项目根目录安装：

```bash
pip install -e .
```

如果需要开发依赖：

```bash
pip install -e ".[dev]"
```

初始化用户目录：

```bash
bamboo init
```

初始化后会创建 `~/.bamboo`，主要配置文件位于：

```text
~/.bamboo/configs/models.yaml
~/.bamboo/configs/bamboo_main_agent.yaml
```

在 `~/.bamboo/configs/models.yaml` 中配置模型，例如：

```yaml
default_model: deepseek-chat

models:
  deepseek-chat:
    provider: deepseek
    model: deepseek-chat
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: https://api.deepseek.com/v1
    timeout: 60
    temperature: 0.2
    context_window: 128000
    max_tokens: 4096
```

然后设置对应的 API Key：

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

当前支持的 provider：

- `deepseek`
- `minimax`
- `gpt`
- `claude`

## 使用 Bamboo 命令

查看版本：

```bash
bamboo version
```

运行单次任务：

```bash
bamboo run "端到端运行检查"
```

启动命令行会话：

```bash
bamboo main
```

带初始消息启动会话：

```bash
bamboo main --msg "帮我分析这个项目"
```

使用项目模式：

```bash
bamboo main --session-mode project --project /path/to/project
```

启动 Web 对话入口：

```bash
bamboo web
```

默认访问地址：

```text
http://127.0.0.1:8765
```

指定 Web 端口：

```bash
bamboo web --port 9000
```

Web 界面支持：

- `Chat`：普通对话模式。
- `Project`：项目上下文模式。
- 左侧历史会话列表，点击后可以继续对话。

管理 Skill：

```bash
bamboo skill list
bamboo skill show skill-creator
bamboo skill create my-skill --description "自定义技能"
```
