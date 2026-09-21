"""Standalone execution request for github_cli.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"command":"parse","repository":"openai/openai-python"}''')
MOCK_ARGS = json.loads(r'''["parse","openai/openai-python"]''')

if __name__ == "__main__":
    run_script(__file__, "github_cli.py", MOCK_ARGS, MOCK_REQUEST)



