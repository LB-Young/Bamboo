#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "zhihu-reach"
PATH = "/story/api/hotKeyword/list"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch RedFoxHub aggregated top10 hotspot events.")
    parser.add_argument("start_datetime", help="yyyy-MM-dd HH:mm:ss")
    parser.add_argument("end_datetime", help="yyyy-MM-dd HH:mm:ss")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {
        "startDate": args.start_datetime,
        "endDate": args.end_datetime,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
