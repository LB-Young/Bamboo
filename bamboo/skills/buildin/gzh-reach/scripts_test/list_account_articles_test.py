"""Standalone execution request for list_account_articles.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"account":"mock-account","offset":0}''')
MOCK_ARGS = json.loads(r'''["--account","mock-account","--offset","0"]''')

if __name__ == "__main__":
    run_script(__file__, "list_account_articles.py", MOCK_ARGS, MOCK_REQUEST)



