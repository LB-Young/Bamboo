#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "bilibili-reach"
PATH = "/story/api/bili/data/listWorkByAccount"


def main() -> int:
    parser = argparse.ArgumentParser(description="List Bilibili UP videos through RedFoxHub.")
    parser.add_argument("--mid")
    parser.add_argument("--account-url")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--order", default="time")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {
        "mid": args.mid,
        "accountUrl": args.account_url,
        "page": args.page,
        "pageSize": args.page_size,
        "order": args.order,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
