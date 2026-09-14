#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bamboo.skills.buildin.redfox_client import handle_cli, post

SKILL = "youtube-reach"
PATH = "/story/api/youtube/videoDetail"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch YouTube video details through RedFoxHub when available.")
    parser.add_argument("video_id_or_url")
    args = parser.parse_args()
    value = args.video_id_or_url
    payload = {"url": value} if value.startswith("http") else {"videoId": value}
    return handle_cli(lambda: post(SKILL, PATH, payload))


if __name__ == "__main__":
    raise SystemExit(main())
