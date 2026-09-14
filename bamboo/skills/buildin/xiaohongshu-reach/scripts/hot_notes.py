#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import get, handle_cli, post

SKILL = "xiaohongshu-reach"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Xiaohongshu RedFoxHub hot-note data.")
    parser.add_argument("--kind", choices=["daily", "weekly", "search", "dark-horse", "hot-accounts"], default="search")
    parser.add_argument("--keyword")
    parser.add_argument("--rank-date")
    parser.add_argument("--category")
    parser.add_argument("--date-type", type=int, help="For hot-accounts: 1=day, 2=week, 3=month.")
    parser.add_argument("--type")
    parser.add_argument("--page-num", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    args = parser.parse_args()
    if args.kind == "daily":
        return handle_cli(lambda: get(SKILL, "/story/api/cozeSkill/getXhsCozeSkillDataOne", {
            "rankDate": args.rank_date,
            "category": args.category,
        }))
    if args.kind == "weekly":
        return handle_cli(lambda: get(SKILL, "/story/api/cozeSkill/getXhsCozeSkillDataSeven", {
            "rankDate": args.rank_date,
            "category": args.category,
        }))
    if args.kind == "dark-horse":
        return handle_cli(lambda: post(SKILL, "/story/api/cozeSkill/getLowPowderExplosiveArticle", {
            "keyword": args.keyword,
            "startDate": args.start_date,
        }))
    if args.kind == "hot-accounts":
        return handle_cli(lambda: post(SKILL, "/story/api/xhsData/query", {
            "dateType": args.date_type,
            "rankDate": args.rank_date,
            "type": args.type,
        }))
    return handle_cli(lambda: post(SKILL, "/story/api/xhs/search/search", {
        "keyword": args.keyword,
        "pageNum": args.page_num,
        "pageSize": args.page_size,
        "startDate": args.start_date,
        "endDate": args.end_date,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
