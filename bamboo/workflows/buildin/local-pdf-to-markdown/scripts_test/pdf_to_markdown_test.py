"""Standalone execution request for pdf_to_markdown.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"pdf":"./mock-input.pdf","output":"./mock-output/article.md","layout_device":"auto"}''')

MOCK_ARGS = json.loads(r'''["./mock-input.pdf","./mock-output/article.md","--layout-device","auto"]''')

if __name__ == "__main__":
    run_script(__file__, "pdf_to_markdown.py", MOCK_ARGS, MOCK_REQUEST)


