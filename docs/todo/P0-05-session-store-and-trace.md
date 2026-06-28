# P0-05 Session Store And Trace

## 目标

把 session、messages、events、tasks 持久化到用户空间，支持恢复、回放和问题定位。

## 背景

当前 `InMemoryTaskStore` 只保存内存快照。多轮对话、工具调用、压缩、错误恢复缺少稳定轨迹。

## 参考

- Auton：SessionStore 区分 project/date。
- Hermes Agent：session lifecycle hooks 和 session commit。
- OpenCode：保存 message finish/error 等执行状态。

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

1. 新增 `bamboo/runtime/session_store.py`。
2. 实现 project/chat 两种 scope 的 session 路径解析。
3. 每次 `Session.add_message` 后可 append 到 `messages.jsonl`。
4. EventBus 增加 `TraceRecorder`，订阅所有事件写入 `events.jsonl`。
5. TaskRuntime 状态变化写入 `tasks.jsonl`。
6. CLI 增加最小 `--resume <session_id>` 或先提供内部 API。
7. 增加 replay 脚本或测试工具读取 jsonl 重建执行链。

## 验收标准

- 一次任务结束后用户空间有 session.json/messages.jsonl/events.jsonl。
- 失败任务也能保存完整轨迹。
- 不影响现有 CLI 输出。
- 测试可用临时 HOME 验证文件生成。

## 非目标

- 不做数据库。
- 不做 Web UI。
