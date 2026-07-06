# P2-08 Cron Main Session Delivery

## 排期信息

- 建议顺序：3
- 建议阶段：P1 - 核心用户能力
- 重要程度：中高
- 优先级：P1
- 依赖关系：依赖已完成的 `docs/agent-trace-events.md`，方便 Web/CLI 稳定消费 cron 投递事件。

## 功能定位

这是定时任务结果投递到真实会话的能力。当前 cron 可以创建和执行任务，但 `session=main` 还只是固定 session id，不能把结果投递回一个活跃主会话。该需求完成后，cron 可以区分 isolated 执行和 main 会话投递，Web/CLI 用户能看到定时任务输出。

## 当前状态

部分完成。

当前已实现：

- `CronScheduler`
- `HeartbeatRunner`
- `~/.bamboo/cron/jobs.yaml`
- retry/backoff
- `cron_*` 对话工具
- cron run jsonl 日志

但 roadmap 中的 `session=main` 还没有完整实现。目前 `session=main` 本质上只是使用固定 session_id 构造 `RunParams`，还没有把结果投递回一个真实的活跃主会话 UI/线程。

## 目标

让 cron job 支持两种真正不同的投递模式：

- `isolated`：创建独立 session/task。
- `main`：把任务结果投递到指定主会话，Web/CLI 可以看到该定时任务输出。

## 需要修改的文件

- `bamboo/cron/models.py`
  - 明确 `session_id` / `delivery` 字段。
- `bamboo/cron/scheduler.py`
  - `session=main` 时查找目标 session。
  - 把 cron 触发事件和最终结果写入目标 session。
- `bamboo/memory/session_store.py`
  - 增加查找活跃/最近 session 的能力。
- `bamboo/adapters/web/app.py`
  - Web SSE 能接收 main-session cron 事件。
- `bamboo/adapters/cli/main.py`
  - CLI interactive session 可以订阅 cron 投递事件。
- `tests/test_cron_main_session_delivery.py`
  - 覆盖 cron 输出投递到已有 session。

## 验收标准

- `session=isolated` 不污染主会话。
- `session=main` 可以把 cron 输出追加到指定 session。
- Web/CLI 订阅者能看到 cron task start/result。
- 目标 session 不存在时失败记录写入 cron logs，不丢失错误。
