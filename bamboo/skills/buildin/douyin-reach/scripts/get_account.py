#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "douyin-reach"
PATH = "/story/api/dyData/queryUser"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Douyin account details through RedFoxHub.")
    parser.add_argument("account_id", help="Douyin unique_id, short_id, uid, or account id.")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {"accountId": args.account_id}))


if __name__ == "__main__":
    raise SystemExit(main())
