# Bamboo Adapters

Bamboo adapters connect external interaction surfaces to the same `TaskRuntime`.
Each adapter normalizes user input into `RunParams`, runs a task, and returns or
streams the result through its own UI.

## Available Adapters

| Adapter | Command | Main use |
| --- | --- | --- |
| CLI interactive | `bamboo main` | Local terminal chat and project sessions |
| CLI one-shot | `bamboo run "task"` | Scripts, quick checks, automation |
| Web | `bamboo web` | Browser chat with streaming events and permission approval |
| Fancy Web | `bamboo web-fancy` | Polished browser UI using the fancy static frontend |
| HTTP API | `bamboo api` | Platform-neutral HTTP API for external channels and services |
| Desktop App | `bamboo app` | PyWebView native shell without a separate HTTP server |
| Fancy Desktop App | `bamboo app-fancy` | Desktop workspace UI with Diff, logs, context meter, model switcher, and themes |
| WeChat | `bamboo wechat` | Personal WeChat text bot using iLink QR login |

## Session Modes

Bamboo supports `chat`, `project`, and `auto` session modes.

- `chat` stores memory under the date-scoped chat memory path.
- `project` stores memory under the selected project memory path and uses the project-aware prompt.
- `auto` resolves according to the entrypoint and project path.

Project-aware adapters should pass an explicit `--project` path when the user
expects file tools, Git Diff, or project memory to apply to a specific repo.

## HTTP API Adapter

Start it with:

```bash
bamboo api
bamboo api --host 0.0.0.0 --port 8898
```

Endpoints:

- `GET /health`: health check.
- `POST /v1/chat`: run one turn and return the final assistant message.
- `POST /v1/chat/stream`: run one turn and stream JSONL runtime events.

Request fields include `message`, `images`, `image_paths`, `mode`,
`project_path`, `session_id`, `record_dir`, `model`, `provider`, `permission`,
and `yes_all`. `images` and `image_paths` are explicit image sources; image-like
URLs or paths in `message` follow the same automatic parsing behavior as other
adapters.

## Fancy Desktop App

Start it with:

```bash
bamboo app-fancy
bamboo app-fancy --session-mode project --project /path/to/project
```

Notable UI behavior:

- `Light` / `Dark` theme switch is stored in browser `localStorage`.
- The `Context` panel uses three images for context usage:
  - calm: `0-39%`
  - warning: `40-89%`
  - critical: `90-100%`
- The Diff view is Git-backed. It lists files from `git status --porcelain`,
  renders tracked and staged diffs with `git diff` / `git diff --cached`, and
  synthesizes a new-file diff for untracked files visible to Git.
- Ignored files, files outside the selected project repository, and non-Git
  directories do not appear in the Diff panel.

## WeChat Adapter

Start it with:

```bash
bamboo wechat
bamboo wechat --relogin
bamboo wechat --session-mode project --project /path/to/project
```

Behavior:

- Uses WeChat iLink QR login.
- Stores token state in `~/.wxbot/token.json`.
- Polls user text messages and replies with Bamboo task output.
- Maintains one in-process Bamboo session per WeChat `from_user_id`.
- Supports `/new` and `/reset` to start a new session for that user.
- Splits long replies into chunks of up to 3000 characters.

Current limitation: this adapter only handles text messages. Image, file, video,
and interactive permission approval can be added later on top of the same
adapter package.

Permission note: by default `bamboo wechat` uses `permission=default`. Read tools
run normally; tools that require confirmation are denied by the non-interactive
permission resolver unless `--yes` or a bypass permission mode is explicitly
used.

## Development Notes

When adding a new adapter:

1. Add a package under `bamboo/adapters/<name>/`.
2. Convert external input into `RunParams`.
3. Use `TaskRuntime.create_task()` for the first turn and
   `TaskRuntime.create_followup_task()` for later turns.
4. Keep permission behavior explicit for non-interactive surfaces.
5. Add the package to `pyproject.toml` under `[tool.setuptools].packages`.
6. Add a CLI command in `bamboo/run.py` when the adapter should be user-facing.
