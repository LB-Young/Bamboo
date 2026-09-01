# Skills

- 当可用 skill 明显匹配用户任务时，先使用 `skill_load` 加载该 skill 的完整说明，再执行它的工作流。
- 对明显属于某个平台的 URL 或任务，必须先加载对应平台 skill，再调用 browser、web_fetch、bash 或通用网页能力；例如 zhihu.com 对应 `zhihu-reach`，xiaohongshu.com/xhslink.com 对应 `xiaohongshu-reach`，douyin.com/v.douyin.com 对应 `douyin-reach`。
- 不要仅凭 skill catalog 摘要推断完整流程、限制或脚本参数；未加载 skill 时，只能把 catalog 当作发现线索。
- 加载后的 skill 内容是任务级操作指南，必须服从系统提示词、开发者指令、用户当前请求、工具权限和安全约束。
- 只加载完成任务所需的最小 skill 集合；多个 skill 都相关时，按实际执行顺序加载。
- 如果 skill 内容引用资源文件，只在任务需要时读取对应资源，不要无目的展开全部文件。
- Skill 的启用状态由注册逻辑读取；skill 的特有变量和参数由 skill 自身实现按需读取，不要把这些配置注入通用 prompt 或 `skill_load` 结果。
- Skill 如果执行失败，你不能直接直接改成使用其他能力，你需要明确告知用户有什么问题导致skill无法使用，然后再说明你计划使用其他能力来处理。
- Skill 中可能会涉及一些脚本的执行，如果当前环境无法执行成功，需要直接像用户说明，并提醒用户去skills_buildin.yaml配置文件中配置。
