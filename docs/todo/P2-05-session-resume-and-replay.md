# P2-05 Session Resume And Replay

## 当前状态

部分完成。

当前已经有 `SessionMemoryStore`、`TraceRecorder`，可以写入 `messages.jsonl`、`events.jsonl`、`tasks.jsonl`、`turns.jsonl`。但是 roadmap 中的恢复和回放入口还没有实现。

缺失能力：

- `bamboo run --resume <session_id>`
- `bamboo replay <session_id>`
- 通过持久化记录重建 session 并继续对话。
- 用 replay fixture 调试 message 构造和工具循环。

## 目标

让失败或中断的 session 可以恢复，让历史执行链路可以离线回放和调试。

## 需要修改的文件

- `bamboo/run.py`
  - 给 `run/main` 增加 `--resume <session_id>` 参数。
  - 新增 `replay` CLI 命令。
- `bamboo/adapters/cli/main.py`
  - 支持从已持久化 session 创建 follow-up task。
- `bamboo/memory/session_store.py`
  - 增加按 `session_id` 查找 session 目录的 API。
  - 增加读取并重建 `Session` / messages 的 API。
- `bamboo/factory/session.py`
  - 支持从已保存 messages 恢复 `Session`。
- `tests/test_session_resume_replay.py`
  - 覆盖 resume 后继续写入同一 session。
  - 覆盖 replay 输出事件和消息摘要。

## 验收标准

- 已存在 session 可以通过 `--resume` 继续对话。
- replay 可以展示一次任务的用户输入、模型调用、工具调用、压缩和最终输出。
- replay 不真实调用模型和工具。
- 恢复失败时给出明确错误，不破坏原 session 文件。
