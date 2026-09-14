#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "douyin-reach"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Douyin work details through RedFoxHub.")
    parser.add_argument("--work-id")
    parser.add_argument("--work-url")
    parser.add_argument("--wide", action="store_true", help="Use the wide-coverage endpoint; requires --work-id.")
    args = parser.parse_args()
    if args.wide:
        path = "/story/api/dy/data/workDetail"
        payload = {"videoId": args.work_id}
    else:
        path = "/story/api/dyData/queryWork"
        payload = {"workId": args.work_id, "workUrl": args.work_url}
    return handle_cli(lambda: post(SKILL, path, payload))


if __name__ == "__main__":
    raise SystemExit(main())
