"""Standalone execution request for process_video.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"video":"./mock-video.mp4","output_dir":"./mock-output","device":"auto"}''')

MOCK_ARGS = json.loads(r'''["./mock-video.mp4","--output-dir","./mock-output","--device","auto"]''')

if __name__ == "__main__":
    run_script(__file__, "process_video.py", MOCK_ARGS, MOCK_REQUEST)


