#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "xiaohongshu-reach"
PATH = "/story/api/xhsUser/searchUser"


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Xiaohongshu accounts through RedFoxHub.")
    parser.add_argument("keyword")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--sort-type")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {
        "keyword": args.keyword,
        "offset": args.offset,
        "sortType": args.sort_type,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
