# Feature 1.2：BKN 文件模型和 Loader

## 目标

定义第一版轻量 BKN 包结构，并实现 loader/validator，把 YAML 文件解析成稳定内存模型。

## 需要干什么

- 支持 BKN 包结构：
  - `bkn.yaml`
  - `schema/ontology.yaml`
  - `graph/entities.yaml`
  - `graph/relations.yaml`
  - `sources/platforms.yaml`
  - `operators/*.yaml`
  - `actions/*.yaml`
- 实现 loader，解析 BKN 包为内存对象。
- 实现 validator，校验必填字段、class 是否存在、relation 端点是否存在。

## 为什么

- 第一版不需要 SQLite 图数据库，YAML/JSON 足够验证“对象 + 关系 + 数据源 + action 元数据”是否对 agent 有价值。
- 明确文件模型后，用户可以手工创建个人内容资产、订阅账单、本地项目依赖等轻量知识网络。

## 需要改什么文件

- `pyproject.toml`
  - 确认 `PyYAML` 已存在；当前已经有，无需新增依赖。
  - `tool.setuptools.packages` 增加 `bamboo.bkn`。

## 需要增加什么文件

- `bamboo/bkn/__init__.py`
- `bamboo/bkn/models.py`
  - `BKNDefinition`
  - `BKNOntology`
  - `BKNEntity`
  - `BKNRelation`
  - `BKNSource`
  - `BKNOperator`
  - `BKNAction`
  - `BKNRetrievalMatch`
- `bamboo/bkn/loader.py`
- `bamboo/bkn/validator.py`
- `tests/fixtures/bkn/personal-media/...`
- `tests/test_bkn_loader.py`

## 测试

- loader 成功解析 fixture。
- 缺 class、缺 relation endpoint、禁用网络时给出明确错误。
- validator 错误信息包含文件路径和字段名。

## 验收标准

- loader 能返回稳定的 `BKNDefinition`。
- validator 能阻止明显坏包进入 registry。
