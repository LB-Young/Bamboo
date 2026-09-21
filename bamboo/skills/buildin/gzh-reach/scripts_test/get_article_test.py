"""Standalone execution request for get_article.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"articleUrl":"https://mp.weixin.qq.com/s/mock"}''')
MOCK_ARGS = json.loads(r'''["https://mp.weixin.qq.com/s/mock"]''')

if __name__ == "__main__":
    run_script(__file__, "get_article.py", MOCK_ARGS, MOCK_REQUEST)



