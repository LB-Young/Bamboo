#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "bilibili-reach"
PATH = "/story/api/bili/data/userSearch"


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Bilibili UP accounts through RedFoxHub.")
    parser.add_argument("keyword")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--order", default="follower")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {
        "keyword": args.keyword,
        "page": args.page,
        "pageSize": args.page_size,
        "order": args.order,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
