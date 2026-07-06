# P2-10 Evaluation And Replay Tools

## 排期信息

- 建议顺序：8
- 建议阶段：P2 - 质量工程和高级运行时
- 重要程度：中高
- 优先级：P2
- 依赖关系：建议在 `P2-09 Agent Trace Schema Docs` 后实施；现有 `--resume` / `replay` 初版能力可以作为输入基础。

## 功能定位

这是失败复现、行为回归和模型/prompt 对比的质量工程能力。当前已有 session trace 持久化和 replay 初步入口，但缺少标准 case 格式、runner、报告和 fixture 沉淀。该需求完成后，可以把真实失败样本保存为可重复执行的评估或回放用例。

## 当前状态

未完成。

roadmap 中提到“评估与回放工具”，当前只有 trace 持久化基础，没有形成独立评估命令、失败样本沉淀和 replay fixture。

## 目标

建立最小评估/回放工具链，用于复现失败、比较 prompt/model/tool 行为变化。

## 需要新增的文件

- `bamboo/eval/__init__.py`
- `bamboo/eval/case.py`
- `bamboo/eval/runner.py`
- `bamboo/eval/report.py`
- `tests/test_eval_runner.py`

## 需要修改的文件

- `bamboo/run.py`
  - 增加 `bamboo eval run <case_dir>`。
  - 增加 `bamboo replay <session_id>`，如果 P2-05 已实现则复用其 replay API。
- `docs/eval.md`
  - 说明 case 格式、运行方式和报告格式。

## 建议 case 结构

```text
eval_cases/
  basic-tool-use/
    input.yaml
    expected.yaml
    fixtures/
```

## 验收标准

- 可以运行一个不调用真实模型的 replay case。
- 可以运行一个真实模型评估 case，并输出 pass/fail 和关键事件摘要。
- 失败样本可以保存为 fixture，后续回归测试复用。
