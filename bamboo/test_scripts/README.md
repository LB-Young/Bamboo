# Bamboo Debug Scripts

These scripts are for local VS Code/debugpy debugging. They are not pytest test
cases, and several of them may call the configured LLM in `~/.bamboo`.

## Scripts

- `debug_cli_single_turn.py`: runs one `bamboo main --msg ...` style turn through the CLI adapter and runtime.
- `debug_cli_interactive.py`: starts the interactive CLI loop; type `/exit` to stop.
- `debug_web_server.py`: starts the real Web server and opens the browser.
- `debug_web_flow_smoke.py`: uses FastAPI `TestClient` to hit Web endpoints without binding a network port.
- `debug_replay_flow.py`: lists persisted sessions and replays the latest session without calling the LLM.
- `test_multi_turn.py`: real two-turn model test, kept from earlier work.
- `test_run_main.py`: older direct `bamboo.run.main()` debug entry.

For live Web stream debugging with `debug_web_flow_smoke.py`, set:

```bash
export BAMBOO_DEBUG_WEB_LIVE_STREAM=1
```
