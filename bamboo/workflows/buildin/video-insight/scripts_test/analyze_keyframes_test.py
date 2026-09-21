"""Standalone execution request for analyze_keyframes.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"keyframes_dir":"./mock-keyframes","output":"./mock-output/keyframe_analysis.json","skip_ocr":true,"skip_description":true}''')

MOCK_ARGS = json.loads(r'''["--keyframes-dir","./mock-keyframes","--output","./mock-output/keyframe_analysis.json","--skip-ocr","--skip-description"]''')

if __name__ == "__main__":
    run_script(__file__, "analyze_keyframes.py", MOCK_ARGS, MOCK_REQUEST)


