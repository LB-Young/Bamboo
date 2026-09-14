#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "douyin-reach"


def main() -> int:
    parser = argparse.ArgumentParser(description="List Douyin account works through RedFoxHub.")
    parser.add_argument("--account-id")
    parser.add_argument("--author-url")
    parser.add_argument("--sec-user-id")
    parser.add_argument("--wide", action="store_true", help="Use userId/uniqueName/shortId wide endpoint.")
    parser.add_argument("--user-id")
    parser.add_argument("--unique-name")
    parser.add_argument("--short-id")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--sort-type")
    parser.add_argument("--page-num", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    args = parser.parse_args()
    if args.wide:
        path = "/story/api/dy/data/listWorkByAccount"
        payload = {
            "userId": args.user_id,
            "uniqueName": args.unique_name,
            "shortId": args.short_id,
            "pageNum": args.page_num,
            "pageSize": args.page_size,
            "startDate": args.start_date,
            "endDate": args.end_date,
        }
    else:
        path = "/story/api/dyData/queryWorkList"
        payload = {
            "accountId": args.account_id,
            "authorUrl": args.author_url,
            "secUserId": args.sec_user_id,
            "offset": args.offset,
            "sortType": args.sort_type,
        }
    return handle_cli(lambda: post(SKILL, path, payload))


if __name__ == "__main__":
    raise SystemExit(main())
