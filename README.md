# Bamboo

Bamboo 是一个 Python 实现的个人 Agent 助手框架。当前版本已经跑通了基础执行链路：命令行输入 -> 创建任务 -> Agent OTA 循环 -> 真实模型调用 -> 事件输出 -> 返回结果。

## 环境要求

Bamboo 要求 Python 3.11+。项目里使用了 Python 3.10/3.11 之后才支持的语法和标准库能力，不能用 Python 3.9 的虚拟环境运行。

先确认当前 Python 版本：

```bash
python --version
```

如果当前 `.venv` 是 Python 3.9 或更低，需要用 Python 3.11+ 重新创建虚拟环境，例如：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

确认虚拟环境版本：

```bash
python --version
```

## 安装

在项目根目录执行：

```bash
pip install -e .
```

如果需要开发依赖：

```bash
pip install -e ".[dev]"
```

## 初始化

初始化用户目录：

```bash
python -m bamboo.run init
```

该命令会准备 `~/.bamboo` 下的配置、工具、技能、日志、工作区等目录。

## 运行

先在 `~/.bamboo/configs/models.yaml` 注册模型，并设置所选模型平台的 API Key，例如：

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

直接运行一个任务：

```bash
python -m bamboo.run run "端到端运行检查"
```

或安装后使用命令：

```bash
bamboo run "端到端运行检查"
```

## 模型配置

模型连接参数统一配置在 `~/.bamboo/configs/models.yaml`。包内的 `bamboo/configs/models.yaml` 是空模板，只在初始化用户空间时复制，不作为运行时配置回退。

```yaml
default_model: deepseek-chat

models:
  deepseek-chat:
    provider: deepseek
    model: deepseek-chat
    api_key: ""
    base_url: https://api.deepseek.com/v1
    timeout: 60
    temperature: 0.2
    max_tokens: 4096
```

当前支持的 `provider`：

- `deepseek`
- `minimax`
- `gpt`
- `claude`

Agent 只配置 `models.yaml` 中的模型注册名，例如：

```yaml
model: deepseek-chat
```

主 Agent 的模型名配置在 `~/.bamboo/configs/bamboo_main_agent.yaml`。`TaskRuntime` 初始化时会一次性加载用户配置并创建本次执行共享的 `LLMFactory`，Agent 执行时只按模型名路由已经注册的 Provider Client。

Provider、实际模型 ID、API Key、Base URL 和生成参数都由 `models.yaml` 管理。模板中的 API Key 为空，可以填写实际值，也可以使用 `${ENV_NAME}` 引用；不要把真实 Key 提交到仓库。

查看版本：

```bash
python -m bamboo.run version
```

## 当前执行流程

```text
CLI 输入
  -> RunParams
  -> TaskRuntime
  -> 加载 ~/.bamboo/configs/models.yaml
  -> 初始化本次执行共享的 LLMFactory
  -> TaskFactory 创建 Task / Session / Context
  -> EventBus 发布任务和状态事件
  -> AgentRuntime 执行 OTA 循环
  -> LLMFactory 按模型名选择 Provider Adapter
  -> 模型平台返回结果
  -> TaskRuntime 收尾
  -> CLI 输出结果
```

OTA 指：

```text
Observe -> Think -> Act
```

Agent 会组织系统提示、消息历史和可用工具列表，在 Act 阶段通过 `LLMFactory` 调用配置的真实模型。

## 验证

编译检查：

```bash
python -m py_compile $(find bamboo -name '*.py' -print)
```

运行检查：

```bash
python -m bamboo.run run "hello bamboo"
```

预期能看到类似输出：

```text
task created ...
task status created -> running
agent state observing ...
agent state thinking ...
agent state acting ...
模型返回的文本内容
task status running -> completed
```

## 说明

当前已经包含：

- `TaskRuntime`
- `TaskFactory`
- `EventBus`
- 真实模型调用的 `AgentRuntime`
- 支持 DeepSeek、MiniMax、GPT 和 Claude 的 `LLMFactory`
- 内置 tools：`read`、`write`、`edit`、`glob`、`grep`、`bash`
- 内置 skill：`skill-creator`
- Agent 和 Task 的基础错误恢复机制

后续需要继续接入真实工具调用决策、流式模型输出、持久化 SessionStore 和 Web 入口。
