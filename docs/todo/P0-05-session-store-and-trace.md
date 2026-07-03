# P0-05 Session Store And Trace

## 当前状态

部分完成。

已有 `bamboo/memory/session_store.py`，会保存 `session.json`、`system_prompt.md`、`messages.jsonl`、`compactions.jsonl`，并已接入 `Session.add_message`。但还缺完整 `events.jsonl`、`tasks.jsonl`、resume/replay API，以及和 `EventBus` 绑定的 trace recorder。

## 目标

把 session、messages、events、tasks 持久化到用户空间，支持恢复、回放和问题定位。

## 存储结构

```text
~/.bamboo/sessions/
  projects/{project_hash}/{session_id}/
    session.json
    messages.jsonl
    events.jsonl
    tasks.jsonl
  dates/{yyyy-mm-dd}/{session_id}/
    session.json
    messages.jsonl
    events.jsonl
    tasks.jsonl
```

## 实现步骤

1. 保留并扩展 `bamboo/memory/session_store.py`，不要再新增重复的 session store。
2. 增加 `TraceRecorder`，建议放在 `bamboo/runtime/trace_recorder.py`。
3. `TraceRecorder` 订阅 `EventBus` 所有事件，写入 `events.jsonl`。
4. `TaskRuntime` 在 create/status/error/completed 时写入 `tasks.jsonl`。
5. 把 project/chat 两种 scope 的路径解析集中到一个 helper，避免 Web 和 CLI 各自拼路径。
6. CLI 增加最小 `--resume <session_id>` 或先提供内部 API。
7. 增加 replay 测试工具读取 jsonl 重建执行链。

## 修改文件

- `bamboo/memory/session_store.py`
  - 增加 `append_event()`、`append_task()`、`load_session()`、`load_messages()`。
- `bamboo/runtime/task_runtime.py`
  - 在任务状态变化时写 tasks trace。
- `bamboo/factory/event_bus.py`
  - 支持 recorder 作为普通订阅者接入即可，避免在 EventBus 内部写文件。
- `bamboo/adapters/cli/main.py`
  - 后续增加 `--resume`。
- `tests/test_session_memory_store.py`
  - 补 events/tasks 持久化测试。

## 验收标准

- 一次任务结束后用户空间有 session.json/messages.jsonl/events.jsonl。
- 失败任务也能保存完整轨迹。
- 不影响现有 CLI 输出。
- 测试可用临时 HOME 验证文件生成。

## 非目标

- 不做数据库。
- 不做 Web UI。
