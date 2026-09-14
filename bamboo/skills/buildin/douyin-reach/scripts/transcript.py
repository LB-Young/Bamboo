#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "douyin-reach"


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit or fetch Douyin video transcript extraction through RedFoxHub.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    submit = subparsers.add_parser("submit")
    submit.add_argument("url")
    result = subparsers.add_parser("result")
    result.add_argument("task_id")
    args = parser.parse_args()
    if args.command == "submit":
        return handle_cli(lambda: post(SKILL, "/story/api/parseWork/audioTextExtract/submit/douyin", {"url": args.url}))
    return handle_cli(lambda: post(SKILL, "/story/api/parseWork/audioTextExtract/result/douyin", {"taskId": args.task_id}))


if __name__ == "__main__":
    raise SystemExit(main())
