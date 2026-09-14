#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "youtube-reach"
PATH = "/story/api/youtube/commentList"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch YouTube comments through RedFoxHub when available.")
    parser.add_argument("video_id")
    parser.add_argument("--continuation-token")
    args = parser.parse_args()
    return handle_cli(lambda: post(SKILL, PATH, {
        "videoId": args.video_id,
        "continuationToken": args.continuation_token,
    }))


if __name__ == "__main__":
    raise SystemExit(main())
