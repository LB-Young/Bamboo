"""Standalone execution request for download_video_free.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"url":"https://www.bilibili.com/video/BV1mock","output_dir":"./mock-downloads"}''')
MOCK_ARGS = json.loads(r'''["https://www.bilibili.com/video/BV1mock","--output-dir","./mock-downloads"]''')

if __name__ == "__main__":
    run_script(__file__, "download_video_free.py", MOCK_ARGS, MOCK_REQUEST)


