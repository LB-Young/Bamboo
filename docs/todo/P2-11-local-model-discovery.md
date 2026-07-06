# P2-11 Local Model Discovery

## 排期信息

- 建议顺序：1
- 建议阶段：P1 - 核心用户能力
- 重要程度：高
- 优先级：P1
- 依赖关系：依赖现有 Ollama/vLLM provider、`models.yaml` 配置模型和 CLI 命令入口。

## 功能定位

这是本地模型配置的发现和向导能力。项目已经能调用 Ollama/vLLM，但用户仍需要手写模型配置。该需求完成后，Bamboo 可以显式探测本地服务、输出可复制配置片段，并在用户确认后安全写入用户配置，不影响正常启动链路。

## 当前状态

未完成。

项目已经有 Ollama/vLLM provider 调用能力，但还没有显式 discovery 和配置向导。

缺失能力：

- 通过 Ollama `/api/tags` 发现本地模型。
- 通过 vLLM `/v1/models` 发现本地模型。
- 输出可复制到 `models.yaml` 的配置片段。
- 可选写入用户 `~/.bamboo/configs/models.yaml`，写入前必须备份和确认。

## 目标

让用户不需要手写本地模型配置，也不会在 Bamboo 启动时因为本地服务没开而失败。

## 需要新增的文件

- `bamboo/llms/local_discovery.py`
  - `LocalModelInfo`
  - `OllamaDiscovery`
  - `VLLMDiscovery`
- `bamboo/llms/model_config_writer.py`
  - 可选，把 discovery 结果写入用户配置。
- `bamboo/adapters/cli/models.py`
  - CLI helper：打印 discovery 结果和配置片段。
- `tests/test_local_model_discovery.py`

## 需要修改的文件

- `bamboo/run.py`
  - 增加 `bamboo models discover ollama`
  - 增加 `bamboo models discover vllm`
- `bamboo/llms/factory.py`
  - 可增加显式 `discover_local_models(provider)`。
  - 不要在 `get_client()` 或启动链路中自动探测。
- `bamboo/configs/models.yaml`
  - 补 Ollama/vLLM 示例和 discovery 命令说明。

## 验收标准

- Ollama discovery 可以解析 `/api/tags`。
- vLLM discovery 可以解析 `/v1/models`。
- 网络失败返回结构化错误，不影响 Bamboo 启动。
- 未经用户确认不自动 `ollama pull`，不修改默认模型。
