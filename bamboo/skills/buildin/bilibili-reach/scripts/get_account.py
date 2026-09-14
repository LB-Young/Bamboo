#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "bilibili-reach"
PATH = "/story/api/bili/data/userDetail"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Bilibili UP account details through RedFoxHub.")
    parser.add_argument("mid")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {"mid": args.mid}))


if __name__ == "__main__":
    raise SystemExit(main())
