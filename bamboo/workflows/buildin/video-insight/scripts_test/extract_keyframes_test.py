"""Standalone execution request for extract_keyframes.py; no pytest required."""

import json

from bamboo.testing.mock_script_runner import run_script

MOCK_REQUEST = json.loads(r'''{"video":"C:/Users/LBY/.bamboo/workspace/bili_zOB0DI8/BV1cqeb6gEcz_p1.mp4","output_dir":"C:/Users/LBY/.bamboo/workspace/bili_zOB0DI8/key_frames","scene_threshold":0.35}''')

MOCK_ARGS = json.loads(r'''["C:/Users/LBY/.bamboo/workspace/bili_zOB0DI8/BV1cqeb6gEcz_p1.mp4","--output-dir","C:/Users/LBY/.bamboo/workspace/bili_zOB0DI8/key_frames","--scene-threshold","0.35"]''')

if __name__ == "__main__":
    run_script(__file__, "extract_keyframes.py", MOCK_ARGS, MOCK_REQUEST)


