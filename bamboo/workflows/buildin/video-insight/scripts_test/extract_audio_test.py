"""Standalone execution request for extract_audio.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"video":"./mock-video.mp4","output":"./mock-output/audio.wav","sample_rate":16000}''')

MOCK_ARGS = json.loads(r'''["./mock-video.mp4","--output","./mock-output/audio.wav","--sample-rate","16000"]''')

if __name__ == "__main__":
    run_script(__file__, "extract_audio.py", MOCK_ARGS, MOCK_REQUEST)


