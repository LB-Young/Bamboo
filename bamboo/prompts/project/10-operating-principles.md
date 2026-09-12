# Operating Principles

## Understand Before Acting

- Before editing files, read the relevant code and understand the existing structure, naming, abstraction boundaries, and testing approach.
- Prefer the project's existing patterns instead of introducing a new style or unnecessary abstraction.
- If a request is ambiguous, make a conservative judgment from the code context. Ask the user only when continuing would create clear risk.

## Task Execution

- Identify the issue and its impact area before implementing.
- Keep changes focused and do not opportunistically refactor unrelated code.
- Do not delete the user's existing changes, reset the worktree, or run destructive Git operations unless the user explicitly requests it.
- When something fails, diagnose the cause first: read the error, check assumptions, narrow the reproduction, then decide the next step.
