"""Standalone execution request for list_account_works.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"userId":"mock-user-id","pageNum":1,"pageSize":5}''')
MOCK_ARGS = json.loads(r'''["--user-id","mock-user-id","--page-num","1","--page-size","5"]''')

if __name__ == "__main__":
    run_script(__file__, "list_account_works.py", MOCK_ARGS, MOCK_REQUEST)



