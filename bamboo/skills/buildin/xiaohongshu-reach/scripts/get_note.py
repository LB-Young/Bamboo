#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "xiaohongshu-reach"
PATH = "/story/api/xhsUser/queryWorkDetail"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Xiaohongshu note details through RedFoxHub.")
    parser.add_argument("--work-id")
    parser.add_argument("--work-link")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {"workId": args.work_id, "workLink": args.work_link}))


if __name__ == "__main__":
    raise SystemExit(main())
