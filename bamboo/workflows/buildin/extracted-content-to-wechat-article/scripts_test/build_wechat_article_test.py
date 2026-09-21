"""Standalone execution request for build_wechat_article.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"content_dirs":["./mock-content"],"article_md":"./mock-article.md","output_dir":"./mock-output","no_cover":true}''')

MOCK_ARGS = json.loads(r'''["./mock-content","./mock-article.md","./mock-output","--no-cover"]''')

if __name__ == "__main__":
    run_script(__file__, "build_wechat_article.py", MOCK_ARGS, MOCK_REQUEST)


