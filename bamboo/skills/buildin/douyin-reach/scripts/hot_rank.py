#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "douyin-reach"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Douyin RedFoxHub hot/surge ranks.")
    parser.add_argument("--kind", choices=["daily-hot", "daily-surge", "weekly-surge", "hot-accounts"], default="daily-hot")
    parser.add_argument("--type")
    parser.add_argument("--start-time")
    parser.add_argument("--end-time")
    parser.add_argument("--date-type", help="For hot-accounts: days, weeks, or months.")
    parser.add_argument("--rank-date", help="For hot-accounts: yyyy-MM-dd.")
    args = parser.parse_args()
    if args.kind == "daily-hot":
        path = "/story/api/dy/search/likesRank"
        payload = {"type": args.type, "startTime": args.start_time, "endTime": args.end_time}
    elif args.kind == "daily-surge":
        path = "/story/api/dy/search/getDailyRank"
        payload = {"type": args.type, "startTime": args.start_time}
    elif args.kind == "weekly-surge":
        path = "/story/api/dy/search/getWeeklyRank"
        payload = {"type": args.type, "startTime": args.start_time}
    else:
        path = "/story/api/dyData/query"
        payload = {"dateType": args.date_type, "rankDate": args.rank_date, "type": args.type}
    return handle_cli(lambda: post(SKILL, path, payload))


if __name__ == "__main__":
    raise SystemExit(main())
