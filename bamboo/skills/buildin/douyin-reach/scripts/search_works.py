#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "douyin-reach"


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Douyin works through RedFoxHub.")
    parser.add_argument("keyword")
    parser.add_argument("--wide", action="store_true", help="Use the wide-coverage RedFoxHub endpoint.")
    parser.add_argument("--offset", type=int, default=0, help="Premium library offset, usually increases by 20.")
    parser.add_argument("--sort-type")
    parser.add_argument("--page-num", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    args = parser.parse_args()
    if args.wide:
        path = "/story/api/dy/data/searchWork"
        payload = {
            "keyword": args.keyword,
            "pageNum": args.page_num,
            "pageSize": args.page_size,
            "startDate": args.start_date,
            "endDate": args.end_date,
        }
    else:
        path = "/story/api/dyData/searchArticle"
        payload = {"keyword": args.keyword, "offset": args.offset, "sortType": args.sort_type}
    return handle_cli(lambda: post(SKILL, path, payload))


if __name__ == "__main__":
    raise SystemExit(main())
