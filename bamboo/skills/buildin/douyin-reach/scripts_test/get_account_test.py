"""Standalone execution request for get_account.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"accountId":"mock-account-id"}''')
MOCK_ARGS = json.loads(r'''["mock-account-id"]''')

if __name__ == "__main__":
    run_script(__file__, "get_account.py", MOCK_ARGS, MOCK_REQUEST)



