#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "zhihu-reach"
PATH = "/story/api/hotSpot/getListByPlatformWithKeyword"
ZHIHU_PLATFORM = 9


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Zhihu hotspot keywords through RedFoxHub.")
    parser.add_argument("keywords", help="Comma-separated keywords.")
    parser.add_argument("start_date", help="yyyy-MM-dd")
    parser.add_argument("end_date", help="yyyy-MM-dd")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {
        "keywords": [item.strip() for item in args.keywords.split(",") if item.strip()],
        "platforms": [ZHIHU_PLATFORM],
        "startDate": args.start_date,
        "endDate": args.end_date,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
