#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "xiaohongshu-reach"
PATH = "/story/api/xhsUser/queryAccountDetail"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Xiaohongshu account details through RedFoxHub.")
    parser.add_argument("account_id", help="Xiaohongshu red id/account id.")
    parser.add_argument("--user-id")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {"accountId": args.account_id, "userId": args.user_id}))


if __name__ == "__main__":
    raise SystemExit(main())
