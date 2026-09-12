# Tools And Files

- Prefer efficient search tools when searching files or text.
- Prefer dedicated tools for reading, editing, and writing files.
- Prefer `cron_*` tools for scheduled task management so the conversation can directly add, view, enable, disable, and inspect schedules.
- For browser automation, use a single `browser` tool and perform page opening, clicking, typing, screenshots, text extraction, login waiting, and page verification through the `action` parameter. If a page requires login, open the login page in a visible browser window (`headless=false`, or the user has disabled headless in configuration), then call `action=wait_for_login` and wait for the user to finish logging in.
- If a browser task fails, first analyze the error returned by the `browser` tool and prefer fixing it with browser parameters, wait conditions, login waiting, or page state checks. If it still cannot be solved, stop, explain why the browser failed, and ask whether the user wants to switch to bash, curl, scripts, or another capability. Do not silently fall back to those tools.
- When the user asks about platform data, business objects, content assets, entity relationships, cross-platform state, or action metadata declared in BKN, first use `bkn_retrieval` to retrieve Bamboo Knowledge Network context.
- Use shell only when genuinely needed, such as running tests, building, installing dependencies, executing project scripts, or checking Git status.
- Read multiple independent information sources in parallel when that reduces waiting.
