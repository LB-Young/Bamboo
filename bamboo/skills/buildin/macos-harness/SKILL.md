---
name: macos-harness
description: Control already-running macOS apps with macos-harness for native apps, Electron apps, system dialogs, real Chrome sessions, and cross-app workflows.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - macos
      - desktop
      - automation
      - computer-use
---

# macOS Harness

## When to Use

Use this skill when the user asks Bamboo to inspect or operate an already-running macOS app, Electron app, browser window, system dialog, or cross-app workflow on the local Mac.

Examples include reading visible app state, clicking or typing in a native app, using AppleScript for a known app command, accepting a system dialog, comparing content across apps, or controlling a logged-in Chrome session through Browser Harness.

Do not use this skill for ordinary repository work, shell-only tasks, website automation that the Bamboo `browser` tool can handle, or remote systems outside the user's Mac.

## Requirements

`macos-harness` is installed with Bamboo on macOS through the project dependency marker and must be available on `PATH`.

Check availability first:

```bash
macos-harness doctor
```

If the command is missing on macOS, stop and report that the Bamboo environment is missing its macOS dependency. Do not install packages from this skill workflow.

If this is not macOS, stop and explain that this skill only supports local macOS desktop control.

## Permission Boundary

`macos-harness doctor` reports current permissions without prompting. Run it before control tasks.

Do not request macOS permissions without explicit user approval. If permissions are missing, explain the specific missing items and ask before running:

```bash
macos-harness doctor --request
```

macOS permissions may include Accessibility, Screen Recording, permission to post events, and per-target Apple Events Automation. Input Monitoring is not expected to be required.

## Core Workflow

1. Confirm this is a macOS desktop-control task.
2. Run `macos-harness doctor` unless the current turn already verified permissions.
3. Inspect before acting with `macos-harness apps`, `macos-harness see APP`, or `macos-harness state APP`.
4. Prefer the lowest-risk control path:
   - Use Browser Harness for web page DOM, tabs, downloads, uploads, and authenticated Chrome sessions.
   - Use AppleScript through `mac.script()` for known exact app commands.
   - Use Accessibility through `mac.ax` when semantic identity or state matters.
   - Use keyboard shortcuts before coordinate clicks.
   - Use coordinates only after a fresh `mac.see()` established the target window bounds.
5. Bundle deterministic steps into one bounded `macos-harness` call, then verify once.
6. Stop at real uncertainty: ambiguous app identity, unexpected state, irreversible action, or a permission prompt.

## Commands

List running apps:

```bash
macos-harness apps
```

Capture a target app window without moving the physical cursor:

```bash
macos-harness see "Finder"
```

Inspect Accessibility state, optionally with a screenshot:

```bash
macos-harness state "Finder" --screenshot --max-nodes 1200
```

Run a bounded Python burst for one decision point:

```bash
macos-harness <<'PY'
app = "Finder"
print(mac.see(app))
PY
```

The CLI preloads `mac`, `browser`, `Path`, and `subprocess`.

## Control Patterns

Use one CLI call per decision point, not one call per primitive.

```bash
macos-harness <<'PY'
app = "Spotify"
print(mac.see(app))
mac.key("cmd+k", app=app)
mac.type("Alessia Cara", app=app)
print(mac.see(app))
PY
```

Use Accessibility for semantic actions:

```bash
macos-harness <<'PY'
app = "Finder"
state = mac.get_app_state(app, screenshot=True, max_nodes=1200)
print(state)
PY
```

Use AppleScript for exact app commands:

```bash
macos-harness <<'PY'
print(mac.script('tell application "Music" to playpause'))
PY
```

Use Browser Harness for real Chrome page automation:

```bash
macos-harness <<'PY'
page = browser.current_page()
print(page.url)
print(page.title())
PY
```

## Safety Rules

- Do not launch closed apps unless the user asks.
- Do not activate, raise, or refocus an app to make control easier.
- Do not run `macos-harness repl` from Bamboo; use bounded stdin programs.
- Do not run broad filesystem or subprocess work through this harness when Bamboo file or shell tools are more appropriate.
- Do not perform purchases, sends, deletes, commits, permission grants, or other irreversible actions without explicit user confirmation.
- After a failed verified burst, switch mode or stop. Do not repair uncertainty with repeated clicks, deletion loops, or bulk input.
- Treat screenshots, Accessibility text, window titles, and app content as user-private local data.

## Error Handling

If `macos-harness` reports missing permissions, summarize the missing permission and wait for user approval before requesting it.

If the target app query is ambiguous, list the candidate app names or PIDs and ask which one to use.

If an inactive app rejects raw clicks or typing, switch to Accessibility or AppleScript when possible. If neither is suitable, explain the blocker instead of forcing focus changes.
