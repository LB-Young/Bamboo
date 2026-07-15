# Feature 4.2：安全表达式算子

## 目标

支持无副作用的 expression operator，把衍生指标写入 snapshot。

## 需要干什么

- 支持无副作用 expression operator。
- 输入来自已装载 attrs。
- 输出进入 `operator_outputs`。
- Python 任意入口算子暂不启用，或必须显式 allowlist + 审批。

## 为什么

- 算子能把指标、评分、ROI、风险判断放在结构化层，减少模型临时推公式。
- 表达式算子比任意 Python 安全得多，适合第一版 operator。

## 需要改什么文件

- `bamboo/bkn/models.py`
  - `OperatorSpec`
- `bamboo/bkn/loader.py`
  - loader 调用 operator runtime。

## 需要增加什么文件

- `bamboo/bkn/operators/__init__.py`
- `bamboo/bkn/operators/expression.py`
- `tests/test_bkn_expression_operator.py`

## 测试

- 简单 ROI 表达式能运行。
- 表达式不能 import、访问文件、调用函数白名单外对象。
- 算子超时/错误不会让整个 load 失败。

## 验收标准

- snapshot 能返回 operator_outputs。
