#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "xiaohongshu-reach"


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit or fetch Xiaohongshu comments through RedFoxHub.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    submit = subparsers.add_parser("submit")
    submit.add_argument("opus_id")
    submit.add_argument("--data-num", type=int, default=100)
    result = subparsers.add_parser("result")
    result.add_argument("task_id")
    args = parser.parse_args()
    if args.command == "submit":
        return handle_cli(lambda: post(SKILL, "/story/api/xhs/commentSubmit", {
            "opusId": args.opus_id,
            "dataNum": args.data_num,
        }))
    return handle_cli(lambda: post(SKILL, "/story/api/xhs/commentResult", {"taskId": args.task_id}))


if __name__ == "__main__":
    raise SystemExit(main())
