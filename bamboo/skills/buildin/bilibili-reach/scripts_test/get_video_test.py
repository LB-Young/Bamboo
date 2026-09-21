"""Standalone execution request for get_video.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"bvId":"BV1mock"}''')
MOCK_ARGS = json.loads(r'''["--bv-id","BV1mock"]''')

if __name__ == "__main__":
    run_script(__file__, "get_video.py", MOCK_ARGS, MOCK_REQUEST)



