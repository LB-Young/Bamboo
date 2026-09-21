"""Standalone execution request for search_works.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"keyword":"人工智能","offset":0}''')
MOCK_ARGS = json.loads(r'''["人工智能","--offset","0"]''')

if __name__ == "__main__":
    run_script(__file__, "search_works.py", MOCK_ARGS, MOCK_REQUEST)



