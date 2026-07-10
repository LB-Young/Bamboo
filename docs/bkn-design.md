# Bamboo BKN 平台数据对接能力设计

## 背景

Bamboo 目前已经有三类主要扩展能力：

- `Tool`：给 Agent 提供可执行能力，例如读写文件、搜索记忆、调用 MCP、执行命令。
- `Skill`：给 Agent 提供可按需加载的工作流知识和操作规程。
- `Memory`：给 Agent 提供用户或项目维度的长期知识，主要面向稳定偏好、项目事实和历史结论。

如果要接入平台数据或业务知识网络，仅使用上述三类能力会有边界不清的问题：

- 放到 `Tool`：只能描述“怎么调用”，缺少业务对象、关系、数据来源、算子、行动之间的统一语义模型。
- 放到 `Skill`：容易变成静态说明，不能自然承载可检索的实体关系和动态数据装载。
- 放到 `Memory`：会把平台数据、业务拓扑和个人长期记忆混在一起，后续很难治理权限、刷新、索引和来源。

因此建议新增一个和 `tool`、`skill` 平级的能力：`BKN`，全称可以定义为 `Bamboo Knowledge Network`。BKN 负责把外部平台数据组织成“对象、关系、数据源、算子、行动”的知识网络，让 Bamboo 在执行任务时通过 `bkn_retrieval` 工具按需召回相关业务上下文。

参考 KWeaver 的核心思想，BKN 不应该把所有平台数据复制进 Bamboo，而是遵循：

- 图看关系：BKN 保存实体、实体之间的关系、类型定义和映射配置。
- 动态查数：属性值、实时状态、统计指标优先从平台 API、本地数据库、CSV、JSON 或脚本中动态加载。
- 上下文装载：`bkn_retrieval` 根据用户问题定位实体与关系，再装载必要属性、算子结果和可行动作说明。

## 目标

第一阶段实现一个轻量、个人开发者可落地的 BKN：

1. 在 `~/.bamboo` 下新增 `bkn` 目录，用户可以通过文件声明平台数据网络。
2. 支持扫描并解析 BKN 包，建立实体、关系、数据源、算子、动作的索引。
3. 新增内置只读工具 `bkn_retrieval`，让 Agent 可以按查询召回 BKN 上下文。
4. 将 `bkn_retrieval` 注册到 ToolRegistry，并在 prompt 的工具目录中自然暴露给模型。
5. 提供稳定的 XML/Markdown 输出格式，方便模型基于召回结果推理和决定下一步是否调用其他 Tool。
6. 为后续平台连接器、图数据库、向量索引、动作执行打基础，但第一阶段不强制引入重依赖。

## 非目标

第一阶段不做以下事情：

- 不直接实现完整图数据库运行时。先用文件索引和轻量检索实现最小闭环。
- 不让 `bkn_retrieval` 执行业务 Action。Action 可以先作为上下文说明返回，真正执行仍应通过现有 Tool 或后续专门的 BKN action tool。
- 不自动同步所有外部平台数据。BKN 只维护配置、轻量索引和必要缓存。
- 不把 BKN 内容注入每一轮 system prompt。BKN 应按需召回，避免上下文膨胀。

## 用户目录结构

新增用户空间目录：

```text
~/.bamboo/
  bkn/
    README.md
    personal-media/
      bkn.yaml
      schema/
        ontology.yaml
      graph/
        entities.yaml
        relations.yaml
      sources/
        platforms.yaml
      operators/
        content_roi.yaml
      actions/
        publish.yaml
      docs/
        notes.md
    storage/
      bkn/
        indexes/
        cache/
        audit.jsonl
```

建议目录含义：

- `~/.bamboo/bkn/{network_name}/bkn.yaml`：一个 BKN 网络的入口文件。
- `schema/`：对象类、关系类、属性、可用算子和动作的本体定义。
- `graph/`：实体实例和关系实例。第一阶段用 YAML/JSON 文件，后续可替换为 Neo4j、SQLite 或远程图服务。
- `sources/`：动态数据源配置，例如本地文件、HTTP API、SQLite 查询、脚本。
- `operators/`：只读计算逻辑的声明，例如 ROI、风险分、健康度。
- `actions/`：业务动作的元数据，例如动作名、参数结构、对应 Tool 或 API 映射。第一阶段只返回说明，不执行。
- `docs/`：补充说明，可作为检索内容。
- `~/.bamboo/storage/bkn`：Bamboo 生成的索引、缓存、审计记录，不建议用户手动维护。

需要在 `bamboo/userspace/userspace.py` 的 `dirs` 中新增：

```python
"bkn",
"storage/bkn",
"storage/bkn/indexes",
"storage/bkn/cache",
```

并增加 helper：

```python
def get_user_bkn_dir() -> Path:
    return get_userspace_dir() / "bkn"

def get_bkn_storage_dir() -> Path:
    return get_userspace_dir() / "storage" / "bkn"
```

## BKN 文件模型

### bkn.yaml

```yaml
schema_version: 1
name: personal-media
description: 个人多平台内容、标签、作者和平台资产网络
enabled: true

entrypoints:
  ontology: schema/ontology.yaml
  entities: graph/entities.yaml
  relations: graph/relations.yaml

retrieval:
  default_limit: 5
  max_hops: 2
  include_dynamic_data: true
  include_actions: true
```

### ontology.yaml

```yaml
classes:
  Content:
    description: 文章、视频、笔记、代码案例等内容资产
    id_field: id
    properties:
      title: string
      platform: string
      url: string
      tags: list[string]
    operators:
      - calculate_content_roi
    actions:
      - republish_content

  Platform:
    description: 内容平台，例如 GitHub、知乎、B 站、公众号
    id_field: id
    properties:
      name: string
      type: string

relations:
  PUBLISHED_ON:
    from: Content
    to: Platform
    description: 内容发布在哪个平台
  TAGGED_WITH:
    from: Content
    to: Tag
    description: 内容绑定的主题标签
  REFERENCES:
    from: Content
    to: Content
    description: 内容之间的引用或改写关系
```

### entities.yaml

```yaml
entities:
  - id: content:agent-memory-design
    class: Content
    title: Agent Memory 设计笔记
    platform: github
    url: https://example.com/agent-memory
    tags: [AI Agent, Memory]

  - id: platform:github
    class: Platform
    name: GitHub
    type: code-hosting
```

### relations.yaml

```yaml
relations:
  - from: content:agent-memory-design
    type: PUBLISHED_ON
    to: platform:github
  - from: content:agent-memory-design
    type: TAGGED_WITH
    to: tag:ai-agent
```

### sources/platforms.yaml

```yaml
sources:
  github_stats:
    type: http
    method: GET
    url: https://api.github.com/repos/{owner}/{repo}
    maps_to:
      class: Content
      properties:
        stars: stargazers_count
        forks: forks_count

  local_content_metrics:
    type: file
    path: ~/content-metrics.csv
    key: content_id
```

### operators/content_roi.yaml

```yaml
operators:
  calculate_content_roi:
    description: 根据阅读量、点赞、收藏、转化等指标计算内容 ROI
    input_classes: [Content]
    type: expression
    expression: "(likes + 2 * favorites + 5 * conversions) / max(views, 1)"
```

### actions/publish.yaml

```yaml
actions:
  republish_content:
    description: 将内容同步发布到目标平台
    class: Content
    mode: tool
    tool_name: workflow_run
    arguments_schema:
      content_id: string
      target_platform: string
```

## 运行时能力

### BKNRegistry

新增模块：

```text
bamboo/bkn/
  __init__.py
  models.py
  registry.py
  store.py
  retrieval.py
  loader.py
  validator.py
```

`BKNRegistry` 负责：

- 扫描 `~/.bamboo/bkn/*/bkn.yaml`。
- 过滤 `enabled: false` 的网络。
- 调用 loader 解析 ontology、entities、relations、sources、operators、actions。
- 调用 validator 做基础校验。
- 向 retrieval 暴露网络列表和查询入口。

建议接口：

```python
class BKNRegistry:
    def __init__(self, *, bkn_dirs: list[Path] | None = None, store: BKNStore | None = None) -> None: ...
    def refresh(self) -> None: ...
    def list(self, *, include_inactive: bool = False) -> list[BKNDefinition]: ...
    def get(self, name: str) -> BKNDefinition | None: ...
    def search(self, query: str, *, network: str = "auto", limit: int = 5, max_hops: int = 2) -> list[BKNRetrievalMatch]: ...
```

### BKNStore

`BKNStore` 负责写入 `~/.bamboo/storage/bkn`：

- `indexes/{network}.json`：实体和关系的轻量索引。
- `cache/{network}/...`：动态数据源短期缓存。
- `audit.jsonl`：检索、刷新、解析失败等审计事件。
- `state.json`：网络状态、最近索引时间、错误信息。

第一阶段索引可以只做关键词倒排和邻接表：

```json
{
  "network": "personal-media",
  "entities": {
    "content:agent-memory-design": {
      "class": "Content",
      "title": "Agent Memory 设计笔记",
      "keywords": ["agent", "memory", "设计", "github"]
    }
  },
  "adjacency": {
    "content:agent-memory-design": [
      {"type": "PUBLISHED_ON", "to": "platform:github"},
      {"type": "TAGGED_WITH", "to": "tag:ai-agent"}
    ]
  }
}
```

### BKNRetrieval

`bamboo/bkn/retrieval.py` 实现查询流程：

1. Query Parsing：从用户 query 中提取关键词、实体 ID、可能的 class 名。
2. Entity Match：在实体 ID、标题、描述、标签、docs 文本中做轻量打分。
3. Graph Expansion：根据 `max_hops` 扩展邻居实体和关系。
4. Dynamic Load：按需从 sources 读取实时属性。第一阶段先支持 `file` 和 `static`，HTTP/API 可作为第二阶段。
5. Operator Attach：返回可运行算子的定义或只执行无副作用表达式算子。
6. Action Attach：返回相关 action 的说明、参数结构和推荐调用方式。
7. Render：输出模型容易使用的结构化结果。

返回对象：

```python
@dataclass(frozen=True, slots=True)
class BKNRetrievalMatch:
    network: str
    entity_id: str
    entity_class: str
    score: int
    summary: str
    relations: list[BKNRelation]
    dynamic_data: dict[str, object]
    operators: list[BKNOperator]
    actions: list[BKNAction]
    source_path: str = ""
```

## bkn_retrieval 工具

新增文件：

```text
bamboo/tools/buildin/bkn_retrieval.py
```

工具定义：

```python
class BKNRetrievalTool(Tool):
    name = "bkn_retrieval"
    description = (
        "Retrieve Bamboo Knowledge Network context for platform/business data. "
        "Use it to find entities, relationships, dynamic attributes, operators, and available actions."
    )
    risk_level = "read"
    tags = ("bkn", "read", "retrieval")
```

输入 schema：

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query, entity id, platform object, or business question."
    },
    "network": {
      "type": "string",
      "description": "Optional BKN network name. Use auto to search all active networks."
    },
    "limit": {
      "type": "integer",
      "description": "Maximum result count, 1-20."
    },
    "max_hops": {
      "type": "integer",
      "description": "Relationship expansion depth, 0-3."
    },
    "include_dynamic_data": {
      "type": "boolean",
      "description": "Whether to load dynamic source data when configured."
    },
    "include_actions": {
      "type": "boolean",
      "description": "Whether to include available action metadata."
    }
  },
  "required": ["query"]
}
```

输出示例：

```xml
<bkn_results query="AI Agent 内容表现" network="personal-media" count="1">
  <result index="1" network="personal-media" entity_id="content:agent-memory-design" class="Content" score="8">
    <summary>Agent Memory 设计笔记，发布在 GitHub，标签包含 AI Agent 和 Memory。</summary>
    <relations>
      - content:agent-memory-design -[PUBLISHED_ON]-> platform:github
      - content:agent-memory-design -[TAGGED_WITH]-> tag:ai-agent
    </relations>
    <dynamic_data>
      stars: 42
      forks: 6
      views: 1800
    </dynamic_data>
    <operators>
      - calculate_content_roi: 根据阅读量、点赞、收藏、转化等指标计算内容 ROI
    </operators>
    <actions>
      - republish_content: tool=workflow_run args={content_id, target_platform}
    </actions>
  </result>
</bkn_results>
```

实现上可以参考 `bamboo/tools/buildin/memory_retrieve.py`：

- 支持 `bind_runtime_context(runtime_context, task)`。
- 从 `runtime_context` 取 `bkn_registry`。
- 缺少运行时上下文时返回 `missing_runtime_context`。
- 限制 `limit` 和 `max_hops` 的范围。
- 返回 `ToolResult(content=..., metadata=...)`。

## RuntimeContext 改动

在 `bamboo/runtime/runtime_context.py` 中：

1. 引入 `BKNRegistry` 和 `create_bkn_registry`。
2. `RuntimeContext` 增加字段：

```python
bkn_registry: BKNRegistry | None = None
```

3. `RuntimeContextBuilder.__init__` 增加可注入参数：

```python
bkn_registry: BKNRegistry | None = None
```

4. 默认创建：

```python
self.bkn_registry = bkn_registry or create_bkn_registry()
```

5. `build()` 返回的 `RuntimeContext` 中带上 `bkn_registry`。

这样 `bkn_retrieval` 可以和 `memory_retrieve` 一样在工具执行前绑定当前任务上下文。

## 工具注册改动

在 `bamboo/tools/buildin/__init__.py` 中：

```python
from bamboo.tools.buildin.bkn_retrieval import BKNRetrievalTool
```

并加入 `create_builtin_tools()` 返回列表，建议放在 `BrowserTool()` 或 `MemoryRetrieveTool()` 附近：

```python
BKNRetrievalTool(),
```

对应测试 `tests/test_tool_registry.py` 需要更新：

- `registry.list_names()` 增加 `bkn_retrieval`。
- `by_source.total` 从当前数量加 1。
- `by_risk["read"]` 从当前数量加 1。

## Prompt 改动

不建议把 BKN 内容整体放入 prompt。现有 `AgentPromptBuilder` 会把 ToolRegistry 中所有工具渲染到 `# Available Tools`，因此只要 `bkn_retrieval` 的工具描述写清楚，模型就能按需调用。

可选增强：在 `bamboo/prompts/project/30-tools-and-files.md` 或 shared prompt 中增加一小段规则：

```md
When a user asks about platform data, business objects, connected entities, content assets,
or cross-platform state, use `bkn_retrieval` to load Bamboo Knowledge Network context
before reasoning from assumptions.
```

中文含义是：遇到平台数据、业务对象、关联实体、内容资产、跨平台状态等问题时，优先通过 BKN 召回上下文。

## CLI 和调试命令

第一阶段工具可直接被 Agent 调用，不一定需要 CLI。但为了开发和排错，建议后续增加：

```text
bamboo bkn list
bamboo bkn validate [network]
bamboo bkn index [network]
bamboo bkn search "query" --network personal-media
```

可能涉及：

- `bamboo/adapters/cli/main.py`
- `bamboo/adapters/cli/commands.py`
- 新增 `bamboo/bkn/cli.py`

## 权限与安全

BKN 第一阶段应默认只读：

- `bkn_retrieval.risk_level = "read"`。
- 只允许读取 `~/.bamboo/bkn` 和 `~/.bamboo/storage/bkn` 下的文件。
- 文件路径必须 resolve 后校验在 BKN 根目录内，避免 `../` 越权读取。
- 动态数据源第一阶段建议只支持 `static`、`file`、`csv`、`json`、`sqlite` 中的只读查询。
- HTTP/API 数据源默认关闭或需要配置显式 allowlist。
- Action 只返回元数据，不直接执行。

第二阶段如果要支持 BKN 动作执行，应新增独立工具，例如：

```text
bkn_action_prepare
bkn_action_execute
```

并复用现有 permission policy、audit log 和 tool 风险分级，不要让 `bkn_retrieval` 同时承担读和写。

## 与现有能力的关系

### BKN vs Tool

Tool 是能力执行单元，BKN 是业务知识网络。BKN 可以声明某个业务对象有哪些可用动作，但动作最终仍应映射到 Tool、MCP tool、workflow 或后续 BKN action executor。

### BKN vs Skill

Skill 是流程知识，BKN 是平台数据语义网络。一个 Skill 可以指导 Agent 如何使用某个 BKN，例如“多平台内容复盘流程”；BKN 则提供具体内容资产、平台、标签、指标和可行动作。

### BKN vs Memory

Memory 是用户和项目长期记忆，BKN 是外部平台数据和业务拓扑。Memory 可以记住“用户偏好发布到知乎”，BKN 则回答“哪些内容和知乎、AI Agent 标签、最近阅读增长有关”。

### BKN vs MCP

MCP 主要提供外部工具协议，BKN 提供业务语义层。BKN 的 source/action 可以映射到 MCP tool，但 Agent 不必直接理解多个底层 MCP 的细节。

## 推荐开发步骤

### 第 1 步：用户空间目录

改动：

- `bamboo/userspace/userspace.py`

内容：

- 在 `dirs` 增加 `bkn` 和 `storage/bkn` 相关目录。
- 增加 `get_user_bkn_dir()`、`get_bkn_storage_dir()`。
- 可选：初始化 `~/.bamboo/bkn/README.md`，说明 BKN 包结构。

测试：

- 新增或更新 userspace 初始化测试，断言目录存在。

### 第 2 步：BKN 数据模型和 loader

新增：

- `bamboo/bkn/models.py`
- `bamboo/bkn/loader.py`
- `bamboo/bkn/validator.py`

能力：

- 解析 `bkn.yaml`。
- 解析 ontology、entities、relations。
- 做基础校验：必填字段、关系端点存在、class 存在、schema_version 支持。

测试：

- `tests/test_bkn_registry.py`
- `tests/fixtures/bkn/personal-media/...`

### 第 3 步：Registry 和 Store

新增：

- `bamboo/bkn/registry.py`
- `bamboo/bkn/store.py`

能力：

- 扫描 BKN 网络。
- 建立内存索引。
- 保存 state/index/audit。

测试：

- 启用和禁用网络。
- 解析失败不影响其他网络。
- 索引内容稳定。

### 第 4 步：Retrieval

新增：

- `bamboo/bkn/retrieval.py`

能力：

- 关键词匹配。
- ID 精确匹配。
- 一跳/二跳关系扩展。
- 返回 `BKNRetrievalMatch`。

测试：

- 按标题召回内容。
- 按标签召回内容。
- `max_hops=0/1/2` 返回关系范围不同。
- `limit` 生效。

### 第 5 步：bkn_retrieval Tool

新增：

- `bamboo/tools/buildin/bkn_retrieval.py`

改动：

- `bamboo/tools/buildin/__init__.py`
- `bamboo/runtime/runtime_context.py`
- `tests/test_tool_registry.py`

测试：

- 工具能在 RuntimeContext 中调用。
- 无 BKN 网络时返回 count=0。
- 有 fixture 网络时返回实体、关系、actions。
- metadata 包含 network、entity_id、score、source_path。

### 第 6 步：Prompt 和文档

改动：

- 可选更新 prompt 规则文件。
- 新增用户文档：如何创建 BKN 包、如何通过 Agent 查询。

测试：

- `tests/test_system_prompt.py` 如有快照或断言，需要同步更新。

## 第一阶段最小实现范围

为了快速落地，建议第一版只实现：

- `~/.bamboo/bkn` 目录。
- 单网络或多网络扫描。
- YAML ontology/entities/relations。
- 静态属性召回。
- 一跳/二跳关系扩展。
- `actions` 只作为元数据返回。
- `bkn_retrieval` 只读工具。
- 基础单元测试。

暂缓：

- Neo4j。
- HTTP 动态数据源。
- 表达式算子执行。
- Action 自动执行。
- 向量索引。
- Web UI 管理。

## 后续演进

### 阶段二：动态数据源

- 支持 CSV/JSON/SQLite 只读数据源。
- 支持短 TTL cache。
- 支持 source 级别 enable/disable 和错误审计。

### 阶段三：算子系统

- 支持安全表达式算子。
- 支持 Python 脚本算子但默认禁用，需要权限确认。
- 算子结果进入 `bkn_retrieval` 输出。

### 阶段四：平台连接器

- GitHub、Notion、飞书、B 站、知乎、微信公众号等连接器。
- 连接器负责生成或刷新 entities/relations/source cache。
- 连接器可以作为 MCP、Plugin 或 BKN source provider 实现。

### 阶段五：业务动作闭环

- 新增 BKN action prepare/execute。
- Action 执行后，如果只改变属性值，不更新图，只依赖动态数据源下次读取。
- Action 执行后，如果改变实体关系，例如内容改平台、拆分主题、产生衍生内容，则通过事件或 post-hook 更新 BKN graph。

这对应 KWeaver 的原则：状态、指标、金额、阅读量这类属性不进图；内容之间的引用、平台归属、标签绑定、作者关系这类拓扑变化才更新图。

## 个人多平台内容资产示例

用户问题：

```text
最近 AI Agent 相关内容哪个平台表现最好？有没有值得复投的旧文章？
```

Agent 应调用：

```json
{
  "query": "AI Agent 内容 平台 表现 复投 旧文章",
  "network": "personal-media",
  "limit": 5,
  "max_hops": 2,
  "include_dynamic_data": true,
  "include_actions": true
}
```

BKN 返回：

- 命中的 Content 实体。
- Content 到 Platform、Tag、Author、Related Content 的关系。
- 动态指标，例如 views、likes、stars、favorites。
- ROI 算子说明或结果。
- 可用动作，例如 `republish_content`、`update_content_from_repo`。

Agent 再基于上下文回答：

- 哪些平台表现好。
- 哪些内容值得复投。
- 需要调用哪个 Tool 或 workflow 做下一步。

## 结论

建议为 Bamboo 增加独立的 `BKN` 能力，而不是把平台数据对接塞进 Tool、Skill 或 Memory。BKN 的职责是管理业务对象和平台数据的语义网络，`bkn_retrieval` 则是 Agent 在运行时按需装载这张网络的入口。

第一阶段应保持轻量：文件声明、轻量索引、只读召回、关系扩展、动作元数据返回。这样可以快速验证“图看关系，动态查数”的核心价值，同时不破坏 Bamboo 当前清晰的 Tool/Skill/Memory 架构。
