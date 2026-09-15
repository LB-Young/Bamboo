#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 获取抖音作品内容详情 (广域库)

抖音按内容获取正文详情

**`POST`** `https://redfox.hk/story/api/dy/data/workDetail`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/dy/data/workDetail`

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
| videoId | String | 是 | 作品ID（必填，对应aweme_id） | 7663047997038644499 |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| authorAvatarUrl | String | 作者头像 | — |
| authorName | String | 作者昵称 | — |
| authorSecUid | String | 作者sec_uid | — |
| authorShortId | String | 作者抖音short_id | — |
| authorUid | String | 作者id  | — |
| authorUniqueId | String | 作者抖音unique_id | — |
| collectCount | Integer | 收藏数 | — |
| commentCount | Integer | 评论数 | — |
| content | String | 作品正文/描述 | — |
| coverUrl | String | 作品封面链接 | — |
| duration | Integer | 作品时长-毫秒 | — |
| imageUrlList | Array | 图片列表-图文作品 | — |
| likeCount | Integer | 点赞数 | — |
| opusUrl | String | 作品链接 | — |
| publishTime | String | 作品发布时间 | — |
| shareCount | Integer | 分享数 | — |
| tagList | Array | 话题列表 | — |
| tagId | String | 话题id | — |
| tagName | String | 话题名称 | — |
| videoId | String | 作品id | — |
| videoType | String | 作品类型：0=普通视频, 68=图集, 63=直播录屏等 | — |

---

## 请求示例

```bash
请求参数：
{
  "videoId": "7663047997038644499"
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "data": {
    "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
    "authorName": "罗永浩的十字路口",
    "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
    "authorShortId": "0",
    "authorUid": "3822358551859599",
    "authorUniqueId": "luoyonghao",
    "collectCount": 89,
    "commentCount": 85,
    "content": "无论有没有文化，都推荐小奇和张骏的播客：《有没有文化现象》。 \n@张骏 @脱口秀小奇",
    "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/0905ee9f8ef0469583bdd3f24a692199~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=%2BwrL8p4daOsNux6uN95TWw%2FLQro%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072204413329A20C441D9E4877E092",
    "duration": 39253,
    "imageUrlList": [],
    "likeCount": 1199,
    "opusUrl": "https://www.iesdouyin.com/share/video/7663047997038644499",
    "publishTime": "2026-07-16 17:00:07",
    "shareCount": 59,
    "tagList": [],
    "videoId": "7663047997038644499",
    "videoType": "0"
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
API_URL = 'https://redfox.hk/story/api/dy/data/workDetail'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='获取抖音作品内容详情 (广域库)')
    parser.add_argument('video_id')
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
        'videoId': args.video_id,
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
