# Skills

- When an available skill clearly matches the user's task, first use `skill_load` to load the full skill instructions, then follow that workflow.
- For URLs or tasks that clearly belong to a specific platform, load the corresponding platform skill before calling browser, web_fetch, bash, or other generic web capabilities. For example, zhihu.com maps to `zhihu-reach`, xiaohongshu.com and xhslink.com map to `xiaohongshu-reach`, and douyin.com and v.douyin.com map to `douyin-reach`.
- Do not infer the complete workflow, limits, or script parameters from the skill catalog summary alone. Until a skill is loaded, treat the catalog only as a discovery hint.
- Loaded skill content is task-level operational guidance and must follow the system prompt, developer instructions, the user's current request, tool permissions, and safety constraints.
- Load only the minimal set of skills needed for the task. When multiple skills are relevant, load them in the order they will be used.
- If a skill references resource files, read those resources only when the task needs them; do not expand every file without purpose.
- A skill's enabled state is read by the registration logic. Skill-specific variables and parameters should be read by the skill implementation as needed; do not inject those settings into the general prompt or `skill_load` result.
- If a skill fails, do not silently switch to another capability. Clearly tell the user what prevented the skill from working, then explain which other capability you plan to use.
- Some skills may involve running scripts. If the current environment cannot execute them successfully, tell the user directly and remind them to configure `skills_buildin.yaml`.
