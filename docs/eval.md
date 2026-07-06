# Bamboo Eval And Replay

Eval case 用于把一次真实失败或关键行为保存成可重复检查的样本。Bamboo 支持两种 case：

- `mode: replay`：只读取已持久化的 session fixture，不调用模型或工具。
- `mode: live`：按 `input.yaml` 发起一次真实运行，用于模型、prompt、tool 行为回归。

## Case 结构

```text
eval_cases/
  basic-tool-use/
    input.yaml
    expected.yaml
    fixtures/
      session/
        session.json
        messages.jsonl
        events.jsonl
        tasks.jsonl
        turns.jsonl
```

## Replay Case

```yaml
# input.yaml
mode: replay
session_id: session-a
fixture: fixtures/session
```

```yaml
# expected.yaml
status: passed
min_events: 3
min_turns: 1
min_messages: 2
event_types:
  - task-create
  - step-finish
output_contains:
  - done
max_errors: 0
```

运行：

```bash
bamboo eval run eval_cases/basic-tool-use
```

输出 JSON：

```bash
bamboo eval run eval_cases/basic-tool-use --json
```

## Live Case

```yaml
# input.yaml
mode: live
message: "List project files"
session_mode: project
project: /path/to/project
model: deepseek-chat
permission: default
yes_all: false
```

Live case 会调用当前 Bamboo runtime，因此可能触发模型请求、工具调用和权限审批。适合在本地或 CI 的受控环境中运行。

## 从 Session 导出 Fixture

```bash
bamboo eval export <session_id> eval_cases/failing-case
```

指定 project 或 record dir：

```bash
bamboo eval export <session_id> eval_cases/failing-case --session-mode project --project /path/to/project
bamboo eval export <session_id> eval_cases/failing-case --record-dir /path/to/session/record
```

导出的 `expected.yaml` 使用当前 fixture 的最小事件、消息和 turn 数作为基线。后续可以手动补充 `event_types`、`output_contains`、`max_errors` 等断言。
