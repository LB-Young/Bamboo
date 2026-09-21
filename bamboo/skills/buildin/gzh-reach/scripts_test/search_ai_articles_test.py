"""Standalone execution request for search_ai_articles.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"keyword":"AI","pageNum":1,"pageSize":5}''')
MOCK_ARGS = json.loads(r'''["AI","--page-num","1","--page-size","5"]''')

if __name__ == "__main__":
    run_script(__file__, "search_ai_articles.py", MOCK_ARGS, MOCK_REQUEST)



