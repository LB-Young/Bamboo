"""Standalone execution request for run_video_insight.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"video":"./mock-video.mp4","output_dir":"./mock-output"}''')

MOCK_ARGS = json.loads(r'''["./mock-video.mp4","--output-dir","./mock-output"]''')

if __name__ == "__main__":
    run_script(__file__, "run_video_insight.py", MOCK_ARGS, MOCK_REQUEST)


