#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import get, handle_cli

SKILL = "zhihu-reach"
PATH = "/story/api/hotSpot/getListByPlatform"
ZHIHU_PLATFORM = 9


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Zhihu hot-rank data through RedFoxHub hotspot API.")
    parser.add_argument("start_date", help="yyyy-MM-dd")
    parser.add_argument("end_date", help="yyyy-MM-dd")
    args = parser.parse_args()
    return handle_cli(lambda: get(SKILL, PATH, {
        "platform": ZHIHU_PLATFORM,
        "startDate": args.start_date,
        "endDate": args.end_date,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
