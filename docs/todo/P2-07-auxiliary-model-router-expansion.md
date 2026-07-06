# P2-07 Auxiliary Model Router Expansion

## 一句话说明

让 Bamboo 内部不同“辅助任务”可以使用不同模型，而不是所有事情都挤在主对话模型或 compaction 模型上。

## 为什么要做

现在 Bamboo 已经有主模型 fallback，也有 compaction 专用的辅助路由。但随着能力变多，很多后台任务并不适合都用同一个模型：

- 压缩上下文需要便宜、长上下文、稳定摘要的模型。
- 记忆整理需要擅长抽取结构化事实的模型。
- skill 匹配需要低成本分类/检索型模型。
- 网页抽取需要能处理长文本的模型。
- 图片理解未来可能需要 vision 模型。

如果这些都复用主模型，会有几个问题：

- 主模型失败时，辅助任务也可能一起失败。
- 某个辅助任务 fallback 以后，可能污染其他任务的 fallback 状态。
- 成本不可控，例如每次 memory/skill 判断都调用昂贵主模型。
- 配置不清晰，用户不知道哪个后台任务在用哪个模型。

## 做完以后是什么效果

用户可以在配置里按用途声明辅助模型，例如：

```yaml
auxiliary_models:
  compaction:
    model: qwen-long
    fallbacks: [deepseek-chat]
  memory:
    model: deepseek-chat
    fallbacks: [ollama-local]
  skills_hub:
    model: ollama-local
  web_extract:
    model: qwen-long
  vision:
    model: gpt-vision
```

运行时效果：

- 主对话仍然使用 `model` / `fallback_models`。
- `compaction`、`memory`、`skills_hub` 等后台任务走自己的 route。
- `memory` 的 fallback 失败记录不会影响 `compaction`。
- 用户不配置时，默认复用主模型，不影响现有使用。

## 不做什么

- 不新增新的模型 provider。Ollama/vLLM/OpenAI-compatible 等 provider 已经独立支持。
- 不改工具权限逻辑。
- 不强制所有辅助任务都必须调用模型；能用规则/检索完成的仍然优先不用模型。

## 涉及的能力边界

这个需求只解决“内部辅助任务应该找哪个模型”。

它不负责：

- 模型发现：已由 Local Model Discovery 实现。
- 主模型 fallback：已由 Model Fallback 实现。
- prompt provider 差异：已由 Provider Specific Prompt 实现。

## 建议实现

### 1. 配置层

修改 `bamboo/configs/bamboo_main_agent.yaml`：

- 增加 `auxiliary_models`。
- 每个 key 是一个辅助任务 role。
- 每个 role 可声明：
  - `model`
  - `fallbacks`
  - `temperature`
  - `max_tokens`
  - 可选 `enabled`

建议支持的 role：

- `compaction`
- `memory`
- `knowledge_curator`
- `skills_hub`
- `web_extract`
- `session_search`
- `vision`

### 2. Router 层

修改 `bamboo/llms/router.py`：

- 增加 `route_for_role(role: str)` 或类似 API。
- 保留现有 main route。
- 每个 auxiliary role 有独立 fallback 状态。
- role 未配置时返回 main route。

### 3. RuntimeContext 层

修改 `bamboo/runtime/runtime_context.py`：

- 在 RuntimeContext 中暴露 `llm_router` 或 `auxiliary_router`。
- 提供便捷方法，例如：
  - `runtime_context.model_for("memory")`
  - `runtime_context.client_for("skills_hub")`

### 4. 调用点接入

优先接入真实会用到模型的调用点：

- `bamboo/runtime/context_compactor.py`
  - 改为使用 `compaction` role。
- `bamboo/memory/knowledge_subagent.py`
  - 改为使用 `memory` 或 `knowledge_curator` role。
- `bamboo/skills/hub.py`
  - 如果后续使用模型做 skill 匹配，则使用 `skills_hub` role。

## 需要修改的文件

- `bamboo/configs/bamboo_main_agent.yaml`
- `bamboo/llms/router.py`
- `bamboo/runtime/runtime_context.py`
- `bamboo/runtime/context_compactor.py`
- `bamboo/memory/knowledge_subagent.py`
- `bamboo/skills/hub.py`

## 需要新增的文件

- `tests/test_auxiliary_router.py`

## 验收标准

- 不配置 `auxiliary_models` 时，所有现有测试继续通过。
- `compaction`、`memory`、`skills_hub` 可以各自选择不同模型。
- 某个 auxiliary role 触发 fallback，不影响 main route 和其他 auxiliary role。
- role 配置了不可用模型时，有清晰错误或自动 fallback。
- 测试覆盖“role 未配置复用 main”、“role 独立 fallback”、“配置解析错误”。

