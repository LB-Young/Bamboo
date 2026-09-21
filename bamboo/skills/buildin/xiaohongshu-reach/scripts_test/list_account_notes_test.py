"""Standalone execution request for list_account_notes.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"redId":"mock-red-id","offset":0}''')
MOCK_ARGS = json.loads(r'''["--red-id","mock-red-id","--offset","0"]''')

if __name__ == "__main__":
    run_script(__file__, "list_account_notes.py", MOCK_ARGS, MOCK_REQUEST)



