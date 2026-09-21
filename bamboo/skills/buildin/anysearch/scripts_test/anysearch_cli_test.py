"""Standalone execution request for anysearch_cli.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"query":"Bamboo agent","domain":"general","max_results":3}''')
MOCK_ARGS = json.loads(r'''["search","Bamboo agent","--domain","general","--max-results","3"]''')

if __name__ == "__main__":
    run_script(__file__, "anysearch_cli.py", MOCK_ARGS, MOCK_REQUEST)



