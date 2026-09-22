# Bamboo 功能与使用指南

按当前仓库实现核对，更新于 2026-09-22。命令参数速查见 `bamboo docs` 页面；每条命令也可追加 `--help`。本文说明实际可用的功能；`docs/*design.md` 和 `docs/todo/` 是设计资料，不代表功能均已实现。

<a id="guide-install"></a>

## 安装、初始化与升级

需要 Python 3.12+。在源码目录运行：

```bash
python -m pip install -e .
python -m bamboo init
python -m bamboo version
```

下文的 `bamboo` 都可以替换成 `python -m bamboo`。Windows 提示找不到 `bamboo` 时，先使用模块入口；可用 `python -c "import sysconfig; print(sysconfig.get_path('scripts'))"` 找出应加入 PATH 的 Scripts 目录。

当前随包的 `models.yaml` 和 `bamboo_main_agent.yaml` 默认选择 `deepseek-chat`。初始化后，在 `~/.bamboo/.env` 中填写：

```dotenv
DEEPSEEK_API_KEY=你的密钥
```

也可在启动 Bamboo 的终端设置环境变量。PowerShell：

```powershell
$env:DEEPSEEK_API_KEY = "你的密钥"
python -m bamboo main --msg "你好，请介绍你能做什么"
```

Linux/macOS：

```bash
export DEEPSEEK_API_KEY="你的密钥"
bamboo main --msg "你好，请介绍你能做什么"
```

`~` 指用户主目录，Windows 通常为 `C:\Users\用户名`。已有用户的实际模型选择以本机配置为准。需要浏览器工具时另外运行 `python -m playwright install chromium`；桌面入口还需要操作系统可用的 PyWebView 后端。视频、OCR 等工作流的额外依赖见后文。

升级代码后可重新执行 `python -m pip install -e .`。**重新运行 `bamboo init` 前备份配置**：已有用户目录时 CLI 会询问是否覆盖，拒绝则取消；接受会重建 `configs` 和内置资源目录，包括已有配置。底层资源同步也会刷新这些目录中与随包内容不同的文件，不能把初始化当作只创建缺失文件的操作。用户 `.env` 和已有 cron jobs 文件不会被该创建逻辑覆盖。

<a id="guide-entrypoints"></a>

## 选择入口与常用任务

| 入口 | 用途 | 示例 |
| --- | --- | --- |
| `main` | 交互对话；传 `--msg` 时执行一轮后退出 | `bamboo main` |
| `run` | 简化的一次性 Chat 任务 | `bamboo run "解释这段错误"` |
| `app` / `app-fancy` | 原生桌面窗口 | `bamboo app-fancy` |
| `web` / `web-fancy` | 浏览器界面，默认端口 8899 | `bamboo web --no-browser` |
| `api` | 面向程序的 HTTP API，默认端口 8898 | `bamboo api` |
| `wechat` | iLink 扫码登录的微信文本入口 | `bamboo wechat` |
| `docs` | 本机使用说明页面 | `bamboo docs` |

```bash
bamboo main --session-mode project --project /path/to/repo
bamboo main --msg "检查项目测试失败原因" --project /path/to/repo --session-mode project
bamboo main --msg "说明这张图片" --model kimi-k3 --image /path/to/image.png
bamboo main --msg "列出项目入口" --verbosity full --debug-events
bamboo web --port 9000 --no-browser
bamboo docs --port 9000 --no-server
```

`main` 支持 `--model`、`--provider`、`--permission`、`--yes`、`--no-stream`、`--session-mode`、`--resume` 和 `--record-dir`。`--verbosity` 可选 `simple`（默认）、`medium`、`full`，影响 CLI 展示；`--debug-events` 用于诊断事件。`--image` 可重复传入，需要同时提供消息，并选择支持图像的模型。

`run` 只提供任务位置参数以及 `--image`、`--debug-events`、`--resume`、`--record-dir`，不能套用 `main` 的全部参数。需要指定项目、模型或权限时使用 `main --msg`。

Fancy 桌面支持模型选择、日志、Context 使用率、亮暗主题和 Git Diff。Diff 来源于 Git 工作区：已跟踪、已暂存和 Git 可见的未跟踪文件可显示，忽略文件和仓库之外的文件不会显示。Context 形象按 0–39%、40–89%、90–100% 分级。

微信首次运行扫码，凭据存于 `~/.wxbot/token.json`；`--relogin` 重新登录。当前仅处理文本，同一微信用户在进程内复用会话，发送 `/new` 或 `/reset` 新建会话。

`bamboo wechat` 默认使用 `chat`，仅启动时显式传入 `--session-mode project` 才进入项目模式，例如 `bamboo wechat --session-mode project --project /path/to/repo`。单独传 `--project` 或传 `--session-mode auto` 仍使用 chat。这里的 session-mode 是会话模式，`--model` 则用于选择模型。

<a id="guide-config"></a>

## 模型、配置与用户目录

| 路径（相对 `~/.bamboo`） | 内容 |
| --- | --- |
| `.env` | 本地密钥，供配置中的 `${ENV_NAME}` 引用 |
| `configs/models.yaml` | 模型注册、连接参数、能力、默认模型 |
| `configs/bamboo_main_agent.yaml` | 主模型、备用模型、压缩与辅助模型、工具超时 |
| `configs/tools.yaml` | 沙箱与媒体工具配置 |
| `configs/tools_buildin.yaml` | 内置工具设置，例如浏览器 profile |
| `configs/mcp.yaml`、`configs/mcp.d/*.yaml` | MCP 服务与插件配置片段 |
| `configs/workflows_buildin.yaml` | 内置工作流启用状态、执行参数和依赖说明 |
| `configs/memory.yaml` | 知识整理子代理配置 |
| `prompts/` | 可编辑的系统提示词模板 |
| `skills/`、`commands/`、`workflows/`、`agents/` | 用户扩展 |
| `bkn/` | 知识网络包与平台目录 |
| `storage/`、`memory/` | 会话、索引、状态与记忆 |
| `cron/jobs.yaml` | 定时任务定义 |
| `logs/`、`workspace/` | 日志与工作产物 |

模型注册名是 `models` 下的键，服务端模型 ID 是其中的 `model`，二者可以不同。下面是与当前默认选择一致的最小示例，编辑已有文件时合并条目，不必删掉其他模型：

```yaml
# ~/.bamboo/configs/models.yaml
default_model: deepseek-chat
models:
  deepseek-chat:
    provider: deepseek
    model: deepseek-chat
    model_type: text
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: https://api.deepseek.com/v1
    timeout: 60
    context_window: 128000
    max_tokens: 4096
    capabilities:
      tool_calling: true
      vision: false
      max_parallel_tools: 1
```

```yaml
# ~/.bamboo/configs/bamboo_main_agent.yaml
model: deepseek-chat
fallback_model: ""
compaction_model: ""
tool_call_timeout_seconds: 120
```

`bamboo main --model 注册名` 覆盖本次模型。永久切换时修改主 Agent 的 `model`；同时让 `default_model` 指向希望的默认注册名。仅修改 API Key 不会切换模型。`fallback_model` 用于可重试的限流、服务错误或超时，留空不启用；`compaction_model` 留空复用主模型。`auxiliary_models` 可按 `compaction`、`memory`、`knowledge_curator`、`skills_hub`、`web_extract`、`session_search`、`vision` 配置 `model` 和 `fallbacks`。`compaction_fallback_model` 在随包配置中仍标注为预留项，不应当作已保证生效的独立开关。

支持的 provider 包括 `kimi`、`deepseek`、`minimax`、`mimo`、`gpt`、`claude`、`aliyun`、`openrouter`、`ollama`、`vllm`，以及用于专门协议的 `flux`、`generic_http`、`http_provider`。后者的请求协议不等于通用聊天协议；按随包示例选择合适的模型类型和协议。媒体模型不用于主聊天模型选择。

本地模型不会在启动时自动探测。先启动本地推理服务，再执行：

```bash
bamboo models discover ollama
bamboo models discover ollama --write --set-default
bamboo models discover vllm --base-url http://localhost:8000/v1 --timeout 10
```

`--write` 写入模型配置，`--replace` 替换同名注册，`--yes` 跳过写入确认。发现完成后检查主 Agent 的 `model` 是否也指向本地注册名。模型支持工具调用时，服务端仍需配套的解析器与模板；在配置中声明能力不会为模型增加能力。

<a id="guide-sessions"></a>

## 会话、恢复、回放与记忆

Chat 用于日常对话，Project 用于明确的项目根目录和项目记忆；`auto` 由运行时根据入口信息解析。处理仓库时显式传 `--session-mode project --project ...`，避免把工作关联到错误目录。

```bash
bamboo replay
bamboo replay list
bamboo replay latest
bamboo replay -2
bamboo replay SESSION_ID --json
bamboo main --resume latest
bamboo main --resume SESSION_ID --msg "继续上次的工作"
bamboo main --session-mode project --project /path/to/repo --resume list
bamboo replay SESSION_ID --session-mode project --project /path/to/repo
```

`replay` 离线读取已有记录，不调用模型或工具；`--resume` 恢复历史并继续实际执行，会产生新调用。`latest` / `last` 和负数序号可用于选择会话；`--record-dir` 用来显式定位已有记录。无参数 `replay` 默认列出最近 10 条，`--limit` 调整数量。

会话保存消息、轮次、任务和事件等记录。长期记忆由 `memory_read`、`memory_search`、`memory_update` 操作；例如请求“记住本项目用 pytest 测试”，或“查找以前关于部署的决定”。长期记忆和当前上下文不同：运行时会在上下文压力下压缩对话，完整 trace 用于后续查询和回放。跨会话保留的重要信息应写入记忆或项目文件，不能只依赖当前模型上下文。

`memory_retrieve` 可选择 `knowledge`（整理后的知识）、`source_log`（原始会话证据）或 `all`；`memory_backfill` 从来源记录提炼带出处的内容，追加到可编辑记忆。需要核实历史结论时请求同时检索原始来源，而不只读取摘要。

<a id="guide-tools"></a>

## 工具、权限与沙箱

工具由 Agent 根据请求调用，不是同名的 `bamboo` 子命令。

| 能力 | 主要工具或入口 | 使用方式 |
| --- | --- | --- |
| 文件与代码 | `read`、`write`、`edit`、`glob`、`grep`、`bash` | “查找入口并修复这个错误” |
| Python 语义查询 | `lsp` | 定义、引用、符号和语法诊断；当前基于 Python AST，不是通用语言服务器 |
| 网页与浏览器 | `web_fetch`、`browser` | 获取页面、打开网站、截图、提取内容、点击与输入 |
| 媒体 | `text_to_image`、`image_edit`、`text_to_video` | 指明内容、参考图和输出需求 |
| 扩展 | `skill_load`、`workflow_load`、`workflow_run`、`subagent_run` | 指定技能、工作流或子代理完成任务 |
| 任务跟踪 | `todo_write`、`task_create`、`task_get`、`task_list`、`task_stop` | 跟踪复杂任务；任务快照本身不等于启动持久后台 worker |
| 自动化 | `cron_add`、`cron_list`、`cron_get`、`cron_enable`、`cron_disable`、`cron_runs`、`cron_tick` | 对话中创建任务、查看执行历史 |
| 记忆与知识 | memory 系列、BKN 系列 | 查询和维护长期知识 |

| 权限模式 | 实际行为 |
| --- | --- |
| `default` / `auto` / `strict` | 读操作允许，其他操作请求确认 |
| `read-only` / `readonly` / `deny` | 允许读操作，拒绝非读操作 |
| `bypass` / `yolo` | 对通过基础风险检查的操作跳过确认 |
| `--yes` | 在默认模式族中自动批准权限提示 |

风险检查先于模式处理；被判定为禁止的破坏性操作不会因 `yolo` 或 `--yes` 而放行。微信、API 等非交互入口无法通过普通终端弹窗确认，需要确认的操作默认被拒绝。`auto` 并不表示自动批准全部操作。

```bash
bamboo main --session-mode project --project /path/to/repo --permission read-only
bamboo main --msg "在项目里生成报告" --project /path/to/repo --yes
```

`configs/tools.yaml` 中的 `sandbox` 与权限策略是不同层：默认 `enabled: false`；开启后可设置 `writable_roots`、`network_enabled`、`env_allowlist`。`fail_open: false` 表示操作系统沙箱不可用时失败，设为 true 则可能无沙箱执行。是否支持取决于本机运行环境。

浏览器配置位于 `configs/tools_buildin.yaml` 的 `browser` 下，默认 `headless: true`；调试登录可改为 false。`user_data_dir` 默认 `~/.bamboo/storage/browser/default`，用于保留网站登录状态。Bash 类脚本需要实际可用的 shell，Windows 上不能把 Bash 命令直接当 PowerShell 命令运行。

<a id="guide-skills"></a>

## Skills 与斜杠命令

Skill 是 Agent 按需读取的能力说明，入口文件为 `SKILL.md`；斜杠命令是把固定提示词模板展开为一条用户消息。内置能力包含调试、测试、代码审查、写作、内容平台访问等，实际可用列表通过 CLI 查看：

```bash
bamboo skill list
bamboo skill list --all
bamboo skill create project-review --description "检查项目交付质量"
bamboo skill show project-review
bamboo skill validate project-review
bamboo skill scan /path/to/skill
bamboo skill install /path/to/skill --trust local
bamboo skill disable project-review
bamboo skill enable project-review
```

创建后编辑用户技能目录中的 `SKILL.md`，写清适用场景、输入、步骤、产物和验证方法。安装前会扫描；`--force` 允许绕过非安全扫描结果，`--overwrite` 允许替换同名安装，二者不是正常安装的必需参数。可以对 Bamboo 说“使用 project-review 检查这个项目”，由 `skill_load` 读取说明。

也可在对话中指定技能来源，让 Agent 使用 `skill_installer` 安装；安装完成后用 `skill show` 和 `skill validate` 检查定义及状态。

内置斜杠模板包括 `/commit`、`/changelog`、`/learn`、`/rmslop`。例如：

```bash
bamboo main --msg "/rmslop 请润色这段文字：……"
```

自定义模板保存为 `~/.bamboo/commands/review.md`，或项目 `.bamboo/commands/review.md`：

```markdown
---
name: review
description: 检查指定模块
---
请检查 $ARGUMENTS 的正确性，说明问题所在文件，并给出验证方法。
```

发送 `/review bamboo/eval` 时会替换 `$ARGUMENTS`。同名模板按项目、用户、内置的优先级覆盖。斜杠命令执行的是展开后的提示词，是否调用工具仍受模型决策与权限策略约束。

<a id="guide-workflows"></a>

## 工作流与内容处理

Workflow 把说明与可执行脚本组合起来。当前没有 `bamboo workflow` CLI 命令组；在对话中要求使用某个工作流，Agent 先调用 `workflow_load`，再调用 `workflow_run`。也可以通过 `workflow_installer` 或插件安装工作流。

| 内置工作流 | 输入与产物 | 依赖提示 |
| --- | --- | --- |
| `daily-review` | 项目状态快照 | Bash |
| `local-pdf-to-markdown` | 本地 PDF → Markdown、JSON 中间结果和图片资源 | PyMuPDF、Pillow、PaddleOCR/Paddle；布局/OCR 模型 |
| `video-insight` | 本地视频 → 音频、转写、关键帧、OCR、视觉描述 | ffmpeg、ffprobe；转写、OCR、视觉步骤各自的模型与依赖 |
| `extracted-content-to-wechat-article` | 提取后的内容目录＋文章 Markdown＋封面 → DOCX、规范化 Markdown、资源清单和检查报告 | python-docx、Pillow；可选 matplotlib |

示例请求：“使用 local-pdf-to-markdown，把 /path/to/input.pdf 转为 /path/to/output.md。”视频示例：“使用 video-insight 分析 /path/to/video.mp4，提取转写和关键帧。”默认视频产物放在 `VIDEO_INSIGHT_OUTPUT_DIR` 下的视频子目录，未设置时使用 `~/.bamboo/workspace/video-insight`。

在 `configs/workflows_buildin.yaml` 查看各工作流的 `requirements`、`variables`、`run.timeout` 和 `enabled`。视频转写通过 `VIDEO_INSIGHT_MODEL_DIR` 指向本地模型，可选 `VIDEO_INSIGHT_VISION_MODEL_DIR` 提供视觉模型；支持 `--skip-transcript`、`--skip-vision`、`--skip-ocr` 等参数，具体以 WORKFLOW.md 为准。长任务还要检查全局工具超时。声明依赖不会自动保证依赖已经安装。

自定义目录为 `~/.bamboo/workflows/<name>/WORKFLOW.md` 或项目 `.bamboo/workflows/<name>/WORKFLOW.md`，同名时项目优先于用户，用户优先于内置。最小模板：

```markdown
---
name: project-summary
description: 生成项目摘要
run:
  script: scripts/summary.py
  cwd: .
  timeout: 60
  risk: read
---
先读取工作流说明，再运行脚本。脚本应输出摘要；输入参数通过 arguments 传入。
```

将脚本放在同目录的 `scripts/summary.py`。按脚本实际行为声明风险，产生文件时使用 `write`，不要给写入或联网脚本标注只读。

<a id="guide-agents"></a>

## 子代理与提示词定制

内置 `explorer`、`planner`、`reviewer`、`verifier`、`knowledge-curator` 等角色，由主 Agent 的 `subagent_run` 工具调用。例如：“让 reviewer 审查本次改动，然后汇总问题。”子代理配置可以限制工具、指定模型和工作区方式。

用户定义实际扫描路径是 `~/.bamboo/agents/*.yaml`，项目路径是 `.bamboo/agents/*.yaml`，并非初始化目录列表中的 `subagents/`。项目定义覆盖同名用户和内置定义。

```yaml
name: project-reviewer
description: 检查代码正确性
model: ""
permission: read-only
workspace_mode: read_only
tools:
  read: true
  grep: true
  glob: true
  bash: false
  write: false
  edit: false
```

模型留空时使用运行时的默认路由。提示词模板在用户 `prompts/` 中，按 shared、chat/project、platform、provider 等组织。修改提示词用于定制语言、风格和工作方式；工具权限仍由运行时执行，不能通过提示词替代权限配置。

`workspace_mode` 支持 `shared`、`read_only`、`tempdir`、`worktree`。共享模式使用同一工作区；临时目录或 Git worktree 用于隔离改动，结果中的差异、保留路径与 `merge_required` 用来提示是否还需合并，不能把子代理完成当作改动已自动进入主工作区。实际可用性取决于项目和 Git 环境。

<a id="guide-mcp"></a>

## MCP 与插件

当前 MCP 管理器启动本地 **stdio** 服务。先独立验证服务程序能运行，再在 `~/.bamboo/configs/mcp.yaml` 配置（将示例路径替换为真实服务）：

```yaml
mcp:
  auto_start: true
  servers:
    my-service:
      command: python
      args: ["/absolute/path/to/mcp_server.py"]
      env:
        SERVICE_API_KEY: "${SERVICE_API_KEY}"
      connect_timeout: 60
      timeout: 120
```

密钥放在 `.env` 或启动环境中。默认 `auto_start: false`，只填写 servers 不会启用。启动成功后发现的工具进入 Bamboo 的工具系统，仍受权限控制。不要把远程 HTTP URL 填成 `command`；当前这个配置解析器以 command/args 启动进程。

Plugin 把 Skills、commands、workflows 和 MCP 配置组合成可安装包。目录中必须有 `bamboo-plugin.yaml` 或 `.yml`：

```yaml
name: project-kit
version: "1.0.0"
description: 项目检查工具包
commands:
  - commands/review.md
```

把上节的 review 模板放入该目录的 `commands/review.md`，然后执行：

```bash
bamboo plugin validate /path/to/project-kit
bamboo plugin install /path/to/project-kit
bamboo plugin list
bamboo plugin show project-kit
bamboo plugin remove project-kit
```

可额外声明 `skills`、`workflows` 路径列表和 `mcp: configs/mcp.yaml`；所有引用文件须在包内。安装经过扫描和隔离区，再复制组件到用户空间；MCP 片段安装到 `configs/mcp.d/`。`install --overwrite` 替换组件；`--force` 允许危险扫描结果。卸载默认保留用户修改过的文件，`remove --force` 才删除这些修改。安装 MCP 组件后仍需检查自动启动配置与服务依赖。

<a id="guide-cron"></a>

## 定时任务与执行历史

```bash
bamboo cron add daily-report --schedule "0 1 * * *" --prompt "总结项目进展" --project /path/to/repo
bamboo cron list
bamboo cron start --interval 30
```

**当前调度器使用 UTC**：上例为 UTC 01:00，即北京时间 09:00。表达式为五段：分钟、小时、日、月、星期。`--interval` 是检查间隔秒数，不是任务执行周期。`cron start` 持续运行；`cron tick` 仅检查一次到期任务，并不是强制运行所有任务。

```bash
bamboo cron disable daily-report
bamboo cron enable daily-report
bamboo cron add follow-up --schedule "0 1 * * *" --prompt "继续检查昨日任务" --delivery main --session-id SESSION_ID --record-dir /path/to/session
```

`--session` 和 `--delivery` 支持 `isolated` / `main`，未指定 delivery 时跟随 session；main 投递需要目标会话信息。已有同名任务要用 `--replace` 更新。任务持久化在 `~/.bamboo/cron/jobs.yaml`，更多权限和重试字段可在文件中配置。CLI add 没有 `--yes` 参数；无人值守任务的权限须在任务配置中明确设置。

常用交互入口会启动进程内调度器，退出进程后不会继续常驻；需要长期运行时启动独立 `cron start`。可在对话中要求“查看 daily-report 最近执行记录”，使用 `cron_runs` 查询成功、失败等历史。注册成功只代表任务已保存，不代表已经执行成功。

可在启动环境设置 `BAMBOO_AUTO_CRON=0` 关闭入口的内嵌调度器；已有独立调度进程时尤其应明确由哪个进程负责调度。

<a id="guide-bkn"></a>

## BKN 知识网络

BKN 用来组织业务对象、关系、来源与动作，使 Agent 可以沿关系检索知识。当前同时包含兼容的 `bkn.yaml` 包以及 `bkn/platforms/<platform_id>/` 平台结构。平台结构使用 `manifest.yaml`、`schema.json` 和图数据；旧格式最小包见仓库 `docs/bkn.md`。

```bash
bamboo bkn list
bamboo bkn list --all
bamboo bkn validate
bamboo bkn validate /path/to/network
bamboo bkn index
bamboo bkn search "项目知识" --network auto --limit 5 --max-hops 2
bamboo bkn export NETWORK --format mermaid
bamboo bkn export NETWORK --format markdown --node NODE_ID --depth 1
```

`validate` 检查格式，`index` 刷新索引，`search` 检索并扩展关系，`export` 输出 Mermaid、DOT 或 Markdown。搜索 limit 限制为 1–20，max-hops 为 0–5；导出邻域 depth 为 0–5。输出不自动创建文件，需要时由 shell 重定向保存。

对话示例：“查询 BKN 中这个项目关联的平台和资料，说明引用来源。”Agent 可用 `bkn_retrieval` 查询、`bkn_export` 导图，也可通过 `bkn_ingest` 创建平台草稿、`bkn_ingest_submit` 提交，经权限检查使用 `bkn_update_topology` 更新节点和边。拓扑更新要求 evidence。草稿阶段不等于已进入活动知识库。

当前已包含 `bkn_action_prepare` 和 `bkn_action_execute`：前者只准备执行计划，后者执行平台私有动作脚本并受执行权限控制。因此“BKN 全部只读、动作仅为元数据”是早期设计描述，已经不适用于当前全部功能。执行前应查看准备结果和参数。

`bkn_list_actions` 可列出平台动作，`bkn_update_manifest` 可在权限控制下更新平台 manifest。应先查看已有动作与元数据，再准备具体调用。

<a id="guide-eval"></a>

## Eval：从会话到回归检查

`bamboo eval` 是基于明确断言的检查工具，不包含自动评审回答质量的模型裁判。一个用例目录至少包含 `input.yaml` 和 `expected.yaml`。

### 导出并离线检查

```bash
bamboo replay list
bamboo eval export SESSION_ID ./cases/demo
bamboo eval run ./cases/demo
bamboo eval run ./cases/demo --json
```

项目会话导出时追加 `--session-mode project --project /path/to/repo`，或用 `--record-dir` 定位。非空目标目录默认拒绝覆盖，确实需要替换时使用 `--overwrite`。导出结果包含 `fixtures/session/` 中的会话记录；分享用例前检查其中的对话和工具数据。

```yaml
# cases/demo/input.yaml
mode: replay
fixture: fixtures/session
```

```yaml
# cases/demo/expected.yaml
min_events: 1
min_turns: 1
min_messages: 1
output_contains:
  - "需要在回答中出现的文字"
max_errors: 0
```

导出默认只按原记录生成事件、消息、轮次数量和事件类型条件；请按任务要求修改 expected。`output_contains` 检查回答文本是否包含指定字符串；所有条目都需满足。replay 只读取记录，既不重新运行任务，也不能证明新模型能重复完成旧任务。

### 实际运行模型

手工创建目录及两个 YAML 文件：

```yaml
# input.yaml
mode: live
message: "请只回答 BAMBOO_OK"
model: deepseek-chat
session_mode: chat
permission: read-only
```

```yaml
# expected.yaml
output_contains: [BAMBOO_OK]
final_task_status: completed
max_errors: 0
```

运行 `bamboo eval run 用例目录`。live 会真正调用模型，也可能执行获准的工具；模型和密钥必须配置好。input 还支持 `project`、`provider`、`session_id`、`yes_all`、`no_stream`、`debug_events`；项目模式使用 `session_mode: project`。

| 断言 | 含义 |
| --- | --- |
| `min_events`、`min_turns`、`min_messages` | 对应数量的下限，默认 0 |
| `event_types` | 每种指定事件都需在记录中出现 |
| `output_contains` | 每个字符串都需包含于输出 |
| `max_errors` | 事件、轮次、任务中的错误计数上限；同一故障可能出现在多个层级 |
| `final_task_status` | 仅 live 检查最终任务状态 |
| `status` | 默认 passed；基于前面检查结果追加状态检查 |

当前 `status: failed` 不会把前面失败的断言转换为整体通过，因此不要用它实现“预期失败即成功”的负例测试。所有检查通过退出码为 0，失败为 1，适合 CI。`--json` 便于检查报告结构；报告包含用例、模式、各项检查、计数、记录目录和输出。

<a id="guide-api"></a>

## HTTP API 集成

```bash
bamboo api --host 127.0.0.1 --port 8898
```

参数包括 `--host`、`--port` / `-p`、`--reload`。以下接口由独立 API 入口提供：

| 接口 | 返回 |
| --- | --- |
| `GET /health` | `{"status":"ok"}` |
| `POST /v1/chat` | 最终文本与 session/task ID、记录目录、状态 |
| `POST /v1/chat/stream` | JSONL 事件流，不是 SSE |

PowerShell 调用示例：

```powershell
$body = @{ message = "你好"; mode = "chat"; permission = "read-only" } | ConvertTo-Json
$result = Invoke-RestMethod -Uri http://127.0.0.1:8898/v1/chat -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$result.message
```

curl 示例（Bash）：

```bash
curl http://127.0.0.1:8898/health
curl -N http://127.0.0.1:8898/v1/chat/stream -H 'Content-Type: application/json' -d '{"message":"你好","mode":"chat","permission":"read-only"}'
```

| 请求字段 | 说明 |
| --- | --- |
| `message` | 必填，非空文本；可使用斜杠模板 |
| `images`、`image_paths` | 图像来源字符串列表，默认空 |
| `mode` | `chat` 默认；传 `project` 使用项目模式，其他值当前归一化为 chat |
| `project_path` | 服务端存在的项目目录 |
| `session_id`、`record_dir` | 恢复会话；后续请求沿用前一次返回值 |
| `model`、`provider` | 覆盖模型注册名或 provider |
| `permission`、`yes_all` | 权限模式与自动确认，默认 default / false |
| `debug_events` | 流式接口是否包含调试事件 |

普通响应字段为 `session_id`、`task_id`、`record_dir`、`status`、`message`。续聊时将返回的会话 ID 和记录目录放入下一次请求，并保持正确的 mode/project_path。流式接口先返回 `session`，随后逐行返回事件，末尾为 `complete`；客户端仍需检查任务状态或错误事件，不能仅凭 complete 认定成功。空消息、无效项目路径等会返回 HTTP 400。

当前 API 应用未配置身份认证；默认仅监听本机。绑定 `0.0.0.0` 会扩大访问范围，面向外部服务部署时需要自行提供访问控制。请求中的文件路径都相对于服务端环境，不是调用方电脑。

<a id="guide-media"></a>

## 图像、视频生成与编辑

在 `models.yaml` 注册 `image_generation`、`image_edit`、`video_generation` 类型模型，按协议填写 `extra_body.protocol`；在 `configs/tools.yaml` 选择工具对应的注册名：

```yaml
media_generation:
  text_to_image_model: aliyun-wanx-t2i
  image_edit_model: aliyun-wanx-image-edit
  text_to_video_model: aliyun-wanx-t2v
  output_dir: ~/.bamboo/workspace/media-generation
  poll_interval_seconds: 2
  timeout_seconds: 600
  tool_call_timeout_seconds: 600
```

这些名称对应随包示例，使用前填好对应 provider 的凭据，并确认服务端模型可用。示例请求：“生成一张竹林插画并保存文件”“把这张参考图改成水彩风格”“生成五秒的竹林视频”。工具会按注册协议发起请求、必要时轮询，并保存产物。图像理解使用聊天视觉模型；生成和编辑使用媒体工具，这两类配置应分别完成。

<a id="guide-troubleshooting"></a>

## 排查问题与文档维护

| 现象 | 检查方法 |
| --- | --- |
| 找不到 bamboo 命令 | 使用同一 Python 的 `python -m bamboo`，检查 Scripts/PATH |
| 缺少密钥或模型不存在 | 检查主 Agent 注册名、models 条目、`.env` 和启动环境 |
| 修改模型配置后仍用旧模型 | 检查主 Agent `model`、CLI 覆盖和界面模型选择；重启入口 |
| 工具不执行 | 检查权限拒绝事件、模型工具能力、MCP 启动错误和依赖 |
| 浏览器无法启动 | 安装 Playwright Chromium，检查 profile 与运行环境 |
| 工作流超时 | 检查工作流 timeout、主 Agent 工具超时、模型和外部程序 |
| 恢复找不到会话 | 先 replay list，核对 chat/project 和项目路径，显式指定 record-dir |
| 定时任务时间不对 | 当前调度按 UTC；确保调度进程持续运行 |
| 桌面 Diff 为空 | 项目是否 Git 仓库、文件是否被忽略、是否选中正确目录 |
| BKN 不可用 | 先 bkn validate，再 index，检查 enabled/status 和错误输出 |
| eval 总是不通过 | 查看每项 expected/actual，区分历史记录检查和 live 执行 |

先使用 `bamboo main --verbosity full --debug-events` 或 `bamboo replay SESSION_ID --json` 定位问题，再检查 `~/.bamboo/logs/`。提交故障说明时附版本、入口、复现命令、相关错误，移除密钥和不适合公开的会话内容。

本文是网页“使用指南”章节的源文件。修改后在仓库根目录运行 `python scripts/build_user_guide.py` 同步到 `bamboo docs`；`python scripts/build_user_guide.py --check` 检查是否同步。网页命令参数表位于 `bamboo/adapters/web/static/docs.html`，新增命令时同时维护参数表与本指南。渲染脚本使用 Rich 依赖的 markdown-it-py，不启动 Bamboo 或调用模型。
