"""Standalone execution request for download_video.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"url":"https://www.bilibili.com/video/BV1mock"}''')
MOCK_ARGS = json.loads(r'''["https://www.bilibili.com/video/BV1mock"]''')

if __name__ == "__main__":
    run_script(__file__, "download_video.py", MOCK_ARGS, MOCK_REQUEST)



