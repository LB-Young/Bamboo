"""Standalone execution request for transcribe_audio.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"audio":"./mock-output/audio.wav","output_dir":"./mock-output","device":"auto","model_dir":"./mock-models/whisper"}''')

MOCK_ARGS = json.loads(r'''["./mock-output/audio.wav","--output-dir","./mock-output","--device","auto","--model-dir","./mock-models/whisper"]''')

if __name__ == "__main__":
    run_script(__file__, "transcribe_audio.py", MOCK_ARGS, MOCK_REQUEST)


