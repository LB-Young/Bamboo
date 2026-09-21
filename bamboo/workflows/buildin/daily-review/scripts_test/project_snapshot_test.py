"""Standalone execution request for project_snapshot.sh; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"focus":"检查今天的项目变更","cwd":"./mock-project"}''')

MOCK_ARGS = json.loads(r'''["检查今天的项目变更"]''')

if __name__ == "__main__":
    run_script(__file__, "project_snapshot.sh", MOCK_ARGS, MOCK_REQUEST)


