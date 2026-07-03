# P2-03 Cron And Heartbeat

## 当前状态

未完成。

当前没有 cron scheduler、job store、heartbeat runtime。Cron 必须复用 `TaskRuntime` 和 `PermissionPolicy`，不能绕过已有权限层。

## 目标

支持定时任务和心跳任务，让 Bamboo 可以在未来自动执行 isolated 或 main-session 任务。

## 参考

- Auton cron：jobs.yaml、scheduler、executor、delivery、retry、logs。
- Hermes Agent：cron 安全、session lifecycle hooks。

## 配置建议

```yaml
jobs:
  - name: daily-report
    schedule: "0 9 * * *"
    session: isolated
    prompt: "生成昨日项目报告"
    retry:
      max_attempts: 3
      backoff: exponential
```

## 实现步骤

1. 实现 `CronJob` 配置结构。
2. 实现 `CronScheduler` 读取 `~/.bamboo/cron/jobs.yaml`。
3. 支持 `session=isolated`：创建新 Task。
4. 支持 `session=main`：写入主会话系统事件。
5. 增加 retry/backoff 和 logs jsonl。
6. cron 执行必须走 PermissionPolicy。
7. heartbeat 用于周期性检查待办或继续当前线程。

## 修改文件

- `bamboo/runtime/task_runtime.py`
- `bamboo/helpers/requests_params.py`
- `bamboo/adapters/cli/main.py`

## 新增文件

- `bamboo/cron/__init__.py`
- `bamboo/cron/models.py`
- `bamboo/cron/scheduler.py`
- `bamboo/cron/store.py`
- `tests/test_cron_scheduler.py`

## 验收标准

- 可以注册、启用、禁用 job。
- job 执行日志落盘。
- 失败按指数退避重试。
- cron 不绕过权限策略。

## 非目标

- 不做分布式调度。
- 不做复杂日历解析。
