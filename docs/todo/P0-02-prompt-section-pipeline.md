# P0-02 Prompt Section Pipeline

## 目标

把 system prompt 从最终字符串拼接升级为可调试、可扩展的 section pipeline。

## 背景

当前 Bamboo 已经把 prompt 拆成多个 md 文件，并支持优先读取 `~/.bamboo/prompts`。但运行时仍然直接构造字符串，缺少 section 元数据，也无法清楚知道每段 prompt 的来源、优先级和是否可缓存。

## 参考

- Auton：SystemPromptBuilder 使用 section priority。
- OpenCode：environment、skills、instructions 分段组合。
- Claude Code Source：default/custom/agent/append/override 有明确优先级。
- OpenClaw：system prompt 注入 runtimeInfo、tools、skillsPrompt、sandboxInfo。

## 范围

新增或调整：

- `bamboo/prompts/system_prompt.py`
- `bamboo/runtime/prompt.py`
- `TaskRuntime` 写入 prompt hash 到 metadata。

## 建议接口

```python
@dataclass(slots=True)
class PromptSection:
    name: str
    priority: int
    source: str
    content: str
    cacheable: bool = True

@dataclass(slots=True)
class BuiltSystemPrompt:
    sections: list[PromptSection]
    content: str
    content_hash: str
```

## Section 顺序

1. `00_identity`
2. `10_core_rules`
3. `20_runtime_environment`
4. `30_project_instructions`
5. `40_memory`
6. `50_tools`
7. `60_skills`
8. `70_subagents`
9. `80_mcp`
10. `90_runtime_notes`

## 实现步骤

1. `SystemPromptBuilder` 先构造 `PromptSection` 列表。
2. section 按 priority 排序后渲染成最终字符串。
3. 每个 md 文件作为一个 section，记录 source 为实际路径。
4. 动态环境、项目指令、工具目录也作为 section。
5. `AgentPrompt.render()` 输出 section 名称和来源，便于调试。
6. `TaskRuntime` 创建 task 后记录 `system_prompt_hash`。

## 验收标准

- 能打印每个 prompt section 的 name/source/priority。
- 修改 `~/.bamboo/prompts` 后下一次任务生效。
- 缺失某个 md 文件不会导致启动失败。
- project/chat 模式仍能正确切换。

## 非目标

- 不实现 memory/skills/subagents 的完整内容，只预留 section。
- 不做 prompt UI。
