#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 抖音视频下载

抖音视频下载

**`POST`** `https://redfox.hk/story/api/parseWork/videoDownload/douyin`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/parseWork/videoDownload/douyin`

---

## 请求头

| 名称 | 类型 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| REDFOX_API_KEY | string | 是 | 平台鉴权令牌，每次请求必填 | ak_xxxxxx |
| Content-Type | string | 是 | 请求体数据类型 | application/json |

---

## 请求参数

| 参数 | 类型 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| url | String | 是 | 视频链接 | 4.38 Oxs:/ e@O.xS 06/01 :2pm 如果你听懂了程艾影，那么即便是前奏也能够让你热泪盈眶了🩵 # 赵雷 # 程艾影 # 永远都像初次见你那样 # 署前街少年 # 音乐节现场  https://v.douyin.com/pjE9uqFMK68/ 复制此链接，打开Dou音搜索，直接观看视频！ |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| cover | String | 封面地址 | — |
| desc | String | 内容 | — |
| resources | Array | 全部媒体资源列表（视频、音频、图片等） | — |
| coverUrl | String | 封面链接 | — |
| downloadUrl | String | 下载链接 | — |
| durationSeconds | Integer | 时长（秒） | — |
| type | String | 资源类型：video-视频, audio-音频, mp3-音频, image-图片 | — |
| title | String | 标题 | — |
| videoUrl | String | 视频下载地址 | — |

---

## 请求示例

```bash
请求参数：
{
  "url": "4.38 Oxs:/ e@O.xS 06/01 :2pm 如果你听懂了程艾影，那么即便是前奏也能够让你热泪盈眶了🩵 # 赵雷 # 程艾影 # 永远都像初次见你那样 # 署前街少年 # 音乐节现场  https://v.douyin.com/pjE9uqFMK68/ 复制此链接，打开Dou音搜索，直接观看视频！"
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "data": {
    "cover": null,
    "desc": "如果你听懂了程艾影，那么即便是前奏也能够让你热泪盈眶了🩵 #赵雷  #程艾影  #永远都像初次见你那样  #署前街少年  #音乐节现场",
    "resources": [
      {
        "coverUrl": null,
        "downloadUrl": "https://v9-default.365yg.com/01f071ebad5469cad0a2a1713923aac8/6a61e8db/video/tos/cn/tos-cn-ve-15c000-ce/oYIayjzoivriLzBEA9TxhPAYMMScQh8mFWYnX/?a=0&br=1225&bt=1225&btag=80000e00030000&cd=0%7C0%7C0%7C0&ch=0&cquery=106H&cr=0&cs=0&cv=1&dr=0&ds=3&dy_q=1784797628&dy_va_biz_cert=&feature_id=f5241e7604dff1d9d6c943fd20bd51a2&ft=k7Fz7VVywIiRZm8Zmo~pK7pswApNVpKVvrKoav_jto0g3cI&l=20260723170708FCFAFFBA267571CDEA6B&lr=normal&mime_type=video_mp4&net=5&qs=0&rc=PDQ0PDU0NjpkaTc8O2YzM0BpamxnPHc5cjRmOzMzbGkzNEAvYTMuMTUyXjQxMjQ0NDNeYSNsZGZiMmRrbW1hLS1kLWJzcw%3D%3D",
        "durationSeconds": null,
        "type": "video"
      },
      {
        "coverUrl": null,
        "downloadUrl": "https://p11-sign.douyinpic.com/tos-cn-p-0015c000-ce/owyPIMAjh3ThcMSimzYaxXAXAUr4BLi9vqEGB~tplv-dy-resize-walign-adapt-aq:720:q75.jpeg?lk3s=138a59ce&x-expires=1786006800&x-signature=UTpEzdb2LclxEEQgC5J%2BZsJsPL4%3D&from=327834062&s=PackSourceEnum_AWEME_DETAIL&se=false&sc=cover&biz_tag=aweme_video&l=2026072317070840D2BFE839546F44E46E",
        "durationSeconds": null,
        "type": "image"
      },
      {
        "coverUrl": null,
        "downloadUrl": "https://lf26-music-east.douyinstatic.com/obj/ies-music-hj/7652404344595352357.mp3",
        "durationSeconds": null,
        "type": "audio"
      }
    ],
    "title": "",
    "videoUrl": "https://v9-default.365yg.com/01f071ebad5469cad0a2a1713923aac8/6a61e8db/video/tos/cn/tos-cn-ve-15c000-ce/oYIayjzoivriLzBEA9TxhPAYMMScQh8mFWYnX/?a=0&br=1225&bt=1225&btag=80000e00030000&cd=0%7C0%7C0%7C0&ch=0&cquery=106H&cr=0&cs=0&cv=1&dr=0&ds=3&dy_q=1784797628&dy_va_biz_cert=&feature_id=f5241e7604dff1d9d6c943fd20bd51a2&ft=k7Fz7VVywIiRZm8Zmo~pK7pswApNVpKVvrKoav_jto0g3cI&l=20260723170708FCFAFFBA267571CDEA6B&lr=normal&mime_type=video_mp4&net=5&qs=0&rc=PDQ0PDU0NjpkaTc8O2YzM0BpamxnPHc5cjRmOzMzbGkzNEAvYTMuMTUyXjQxMjQ0NDNeYSNsZGZiMmRrbW1hLS1kLWJzcw%3D%3D"
  },
  "msg": "成功"
}
```

---

## 密钥获取与安全说明

- 本API需要使用API密钥 `REDFOX_API_KEY`。
- API密钥由 [红狐 hub](https://redfox.hk/settings/api-keys?source=redfox_api_md) (`https://redfox.hk`)提供。
- 请前往 [红狐 hub](https://redfox.hk?source=redfox_api_md) 注册并登录账号，在密钥管理模块创建 API密钥。
- 复制并仅在请求头中使用API密钥。
- 在提供密钥前，请先确认密钥来源、可用范围、有效期及是否支持重置/撤销。
- 禁止在代码、提示词、日志或输出文件中硬编码/明文暴露密钥。

"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

from bamboo.helpers.config import load_builtin_skill_variables

SKILL_NAME = 'douyin-reach'
API_URL = 'https://redfox.hk/story/api/parseWork/videoDownload/douyin'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='抖音视频下载')
    parser.add_argument('url')
    args = parser.parse_args(argv)
    try:
        data = call_api(build_payload(args))
    except RedFoxHubError as exc:
        print(f"RedFoxHub error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        'url': args.url,
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def call_api(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = load_api_key()
    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers={
                "REDFOX_API_KEY": api_key,
                "Content-Type": "application/json",
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RedFoxHubError(f"network failure: {exc}") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise RedFoxHubError(f"invalid JSON response from HTTP {response.status_code}: {response.text[:500]}") from exc
    if response.status_code >= 400:
        raise RedFoxHubError(f"HTTP {response.status_code}: {response.text[:1000]}")
    return data


def load_api_key() -> str:
    variables = load_builtin_skill_variables(SKILL_NAME)
    api_key = os.environ.get("REDFOX_API_KEY") or str(variables.get("REDFOX_API_KEY") or "")
    if not api_key:
        raise RedFoxHubError("missing REDFOX_API_KEY; set it in ~/.bamboo/.env or built-in skill variables")
    return api_key


if __name__ == "__main__":
    raise SystemExit(main())
