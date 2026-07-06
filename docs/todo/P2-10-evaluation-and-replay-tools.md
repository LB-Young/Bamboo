# P2-10 Evaluation And Replay Tools

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
