"""Standalone execution request for get_note.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"workId":"mock-work-id"}''')
MOCK_ARGS = json.loads(r'''["--work-id","mock-work-id"]''')

if __name__ == "__main__":
    run_script(__file__, "get_note.py", MOCK_ARGS, MOCK_REQUEST)



