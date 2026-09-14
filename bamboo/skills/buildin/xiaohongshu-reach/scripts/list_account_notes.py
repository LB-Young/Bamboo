#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "xiaohongshu-reach"
PATH = "/story/api/xhsUser/queryWorkList"


def main() -> int:
    parser = argparse.ArgumentParser(description="List Xiaohongshu account notes through RedFoxHub.")
    parser.add_argument("--red-id")
    parser.add_argument("--userid")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--sort-type")
    parser.add_argument("--publish-time-start")
    parser.add_argument("--publish-time-end")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {
        "redId": args.red_id,
        "userid": args.userid,
        "offset": args.offset,
        "sortType": args.sort_type,
        "publishTimeStart": args.publish_time_start,
        "publishTimeEnd": args.publish_time_end,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
