---
name: skill-creator
description: "Create, edit, or improve Bamboo skills. Use when: (1) the user wants to create a new skill, (2) improve or audit an existing skill, (3) the user says 'create a skill', 'build a skill', 'author a skill'. Do not use for simple questions about skills that can be answered directly, or when a skill already exists and the user only wants to use it."
user-invocable: true
load-experiences: true
metadata:
  bamboo:
    emoji: "🛠️"
---

# Skill Creator

Create, edit, or improve skills that extend Bamboo with specialized knowledge, workflows, tool guidance, and reusable resources.

## What Skills Provide

1. **Specialized workflows**: repeatable multi-step procedures for a specific domain.
2. **Tool guidance**: instructions for using Bamboo tools, external CLIs, APIs, or file formats.
3. **Domain knowledge**: project-specific schemas, conventions, business rules, or operational runbooks.
4. **Bundled resources**: scripts, references, templates, examples, and assets for complex work.

## When to Use This Skill

Use this skill when:

- The user asks to create a new skill for a concrete domain or workflow.
- The user wants to improve, tidy, or audit an existing skill.
- The user asks to package reusable instructions as a skill.
- The user says: "create a skill", "build a skill", "author a skill", or "improve this skill".

Do not use this skill when:

- The user only asks a simple conceptual question about skills.
- The user only wants to list, inspect, or invoke an already existing skill.
- The request is better handled by direct code changes, documentation edits, or ordinary tool use.

## Skill Anatomy

Every Bamboo skill is a directory:

```text
<skill-name>/
├── SKILL.md          # Required: YAML frontmatter + Markdown body
├── scripts/          # Optional: executable helper scripts
├── references/        # Optional: detailed docs loaded on demand
├── assets/            # Optional: templates, examples, images, or generated assets
└── experiences/       # Optional: lessons learned while using the skill
    └── README.md      # Experience entries
```

## SKILL.md Format

```yaml
---
name: <skill-name>
description: "What this skill does and when to use it. Be specific about triggers."
user-invocable: true
load-experiences: true
metadata:
  bamboo:
    emoji: "🔧"
    requires:
      bins: ["gh", "jq"]
---

# Skill Name

## When to Use

Use when...
Do not use when...

## Workflow

1. Understand the request.
2. Load only the references needed for the task.
3. Use bundled scripts or assets when they are present.
4. Complete the task and record useful lessons in experiences when appropriate.
```

## Skill Creation Process

1. **Understand the use case**: ask what repeated task or domain the skill should help with.
2. **Identify triggers**: write a description that clearly says when the skill should and should not load.
3. **Choose resources**: decide whether the skill needs scripts, references, assets, or experiences.
4. **Create the directory**: use lowercase letters, digits, and hyphens for the directory name.
5. **Write SKILL.md**: keep the body concise and workflow-oriented.
6. **Add experiences**: create `experiences/README.md` when lessons should be tracked over time.
7. **Validate manually**: check frontmatter, naming, trigger clarity, and whether the skill avoids loading unnecessary context.

## Naming Conventions

- Use lowercase letters, digits, and hyphens only.
- Keep names under 64 characters.
- Prefer names that describe the domain or workflow: `github-review`, `api-debugger`, `spreadsheet-cleanup`.
- Namespace by tool or platform when helpful: `gh-pr-review`, `postgres-maintenance`.

## Quality Principles

- **Concise over verbose**: include what Bamboo needs to behave differently, not general knowledge the model already has.
- **Progressive disclosure**: keep `SKILL.md` lean; put long docs in `references/`.
- **Actionable workflow**: write steps the agent can follow, not marketing copy.
- **Clear trigger boundaries**: include both "use when" and "do not use when".
- **Reusable assets**: put templates, scripts, and examples in subdirectories instead of embedding large blobs in the skill body.
- **Experience tracking**: record lessons that prevent repeated mistakes.

## Audit Checklist

- Frontmatter has `name`, `description`, and `user-invocable`.
- Description includes concrete triggers and exclusions.
- Body explains the workflow clearly.
- Long references are not pasted directly into `SKILL.md`.
- Scripts, references, assets, and experiences are only added when they are useful.
- The skill name matches the directory name.
- The skill does not depend on Bamboo internals unless that dependency is documented.

