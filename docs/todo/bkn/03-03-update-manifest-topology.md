# Feature 3.3：`bkn_update_manifest` 和 `bkn_update_topology`

## 目标

提供受控写工具，让 BKN 可以在用户批准后演化。

## 需要干什么

- 新增受控写工具：
  - `bkn_update_manifest`
  - `bkn_update_topology`
- 写拓扑必须带 evidence/source。
- 写入前校验 manifest status 和 allowlist。

## 为什么

- BKN 需要演化，但不能让 agent 任意改文件。
- 拓扑事实必须有证据链，便于后续回滚、审计和解释。

## 需要改什么文件

- `bamboo/tools/buildin/__init__.py`
  - 注册写工具。
- `bamboo/security/permission_policy.py`
  - 如有必要，为 BKN 写工具设置合适风险级别和审批行为。
- `bamboo/bkn/graph.py`
  - 写入事件审计。

## 需要增加什么文件

- `bamboo/tools/buildin/bkn_update_manifest.py`
- `bamboo/tools/buildin/bkn_update_topology.py`
- `tests/test_bkn_update_tools.py`

## 测试

- status 为 paused/deprecated 时拒绝写入。
- 无 evidence 拒绝写拓扑。
- 写入后 `events.jsonl` 有记录。
- 写工具不是 read risk，需要触发现有 permission 流程。

## 验收标准

- 用户批准后，agent 能新增节点/边，并能通过查询看到更新。
