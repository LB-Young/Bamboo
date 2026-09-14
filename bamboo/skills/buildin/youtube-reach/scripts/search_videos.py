#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "youtube-reach"
PATH = "/story/api/youtube/searchVideo"


def main() -> int:
    parser = argparse.ArgumentParser(description="Search YouTube videos through RedFoxHub.")
    parser.add_argument("query")
    parser.add_argument("--continuation-token")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {
        "searchQuery": args.query,
        "continuationToken": args.continuation_token,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
