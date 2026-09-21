"""Standalone execution request for run.sh; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"arguments":"./mock-input.pdf ./mock-output/article.md"}''')

MOCK_ARGS = json.loads(r'''["./mock-input.pdf ./mock-output/article.md"]''')

if __name__ == "__main__":
    run_script(__file__, "run.sh", MOCK_ARGS, MOCK_REQUEST)


