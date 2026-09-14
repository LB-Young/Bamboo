#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "bilibili-reach"
PATH = "/story/api/bili/data/workDetail"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Bilibili video details through RedFoxHub.")
    parser.add_argument("bvid_or_url")
    args = parser.parse_args()
    value = args.bvid_or_url
    payload = {"workUrl": value} if value.startswith("http") else {"bvid": value}
    return handle_cli(lambda: post(SKILL, PATH, payload))


if __name__ == "__main__":
    raise SystemExit(main())
