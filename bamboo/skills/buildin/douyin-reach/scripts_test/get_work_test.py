"""Standalone execution request for get_work.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"videoId":"mock-video-id"}''')
MOCK_ARGS = json.loads(r'''["mock-video-id"]''')

if __name__ == "__main__":
    run_script(__file__, "get_work.py", MOCK_ARGS, MOCK_REQUEST)



