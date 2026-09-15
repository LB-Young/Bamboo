#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 搜索关键词获取哔哩哔哩作品 (优质库)

搜索关键词获取哔哩哔哩作品 (优质库)

**`POST`** `https://redfox.hk/story/api/bili/data/workSearch`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/bili/data/workSearch`

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
| keyword | String | 是 | （必填，搜索关键词） | 羽绒服 |
| exactMatch | Boolean | 否 | 是否精准匹配（默认false） false: 模糊匹配，关键词分词后部分匹配即可召回 true: 精准匹配，关键词作为完整短语必须包含在作品标题或作者中 | — |
| page | String | 是 | （必填，页码） | 1 |
| pageSize | Integer | 否 | （非必填，每页条数，默认10，最大50） | 10 |
| order | String | 否 | （非必填，排序：time=发布时间/play=播放数/like=点赞数/comment=评论数/favorite=收藏数，默认time） | time |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| code | Integer | 状态码，2000=成功 | 2000 |
| msg | String | 提示信息 | 成功 |
| data | Object |  | — |
| page | Integer | 当前页码 | 1 |
| pageSize | Integer | 每页条数 | 10 |
| total | Integer | 总条数 | 25117 |
| workList | Array | 作品列表 | — |
| author | String | 作者昵称 | Randall-FD |
| authorId | String | 作者ID | 31701874 |
| bvId | String | BV号 | BV1n57e6kEtz |
| coinCount | Integer | 投币数 | 0 |
| commentCount | Integer | 评论数 | 0 |
| created | String | 发布时间 | 2026-06-26 03:03:13 |
| description | String | 视频描述 | https://youtu.be/pJHNYg7DoeI BGM：少年よ 嘘をつけ! … |
| duration | Integer | 时长（秒） | 16 |
| favoriteCount | Integer | 收藏数 | 0 |
| firstType | String | 一级分类 | 游戏 |
| interactionQuantity | Integer | 互动数 | 13 |
| likeCount | Integer | 点赞数 | 12 |
| picUrl | String | 封面 | http://i0.hdslb.com/bfs/archive/3c6d1ef92af603bc82f7e0edf03cbce1a3857164.jpg |
| playCount | Integer | 播放数 | 4 |
| secondType | String | 二级分类 | 网络游戏 |
| shareCount | Integer | 分享数 | 1 |
| tagNames | Array | 作品标签 | — |
| title | String | 作品标题 | 【跑跑卡丁车】【远古视频】日服跑跑宣传视频（走廊奔跑队7） |
| videoReview | Integer | 弹幕数 | 0 |

---

## 请求示例

```bash
请求参数：
{
  "keyword": "羽绒服",
  "page": "1",
  "pageSize": 10,
  "order": "time"
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "msg": "成功",
  "data": {
    "workList": [
      {
        "bvId": "BV1n57e6kEtz",
        "title": "【跑跑卡丁车】【远古视频】日服跑跑宣传视频（走廊奔跑队7）",
        "description": "https://youtu.be/pJHNYg7DoeI\nBGM：少年よ 嘘をつけ! …",
        "duration": 16,
        "picUrl": "http://i0.hdslb.com/bfs/archive/3c6d1ef92af603bc82f7e0edf03cbce1a3857164.jpg",
        "created": "2026-06-26 03:03:13",
        "author": "Randall-FD",
        "authorId": "31701874",
        "firstType": "游戏",
        "secondType": "网络游戏",
        "playCount": 4,
        "likeCount": 12,
        "favoriteCount": 0,
        "commentCount": 0,
        "shareCount": 1,
        "videoReview": 0,
        "coinCount": 0,
        "interactionQuantity": 13,
        "tagNames": [
          "跑跑卡丁车",
          "日服",
          "宣传片",
          "宣传视频"
        ]
      }
    ],
    "page": 1,
    "pageSize": 10,
    "total": 25117
  }
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

SKILL_NAME = 'bilibili-reach'
API_URL = 'https://redfox.hk/story/api/bili/data/workSearch'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='搜索关键词获取哔哩哔哩作品 (优质库)')
    parser.add_argument('keyword')
    parser.add_argument('--exact-match', action='store_true')
    parser.add_argument('--page', default='1')
    parser.add_argument('--page-size', type=int, default=10)
    parser.add_argument('--order', default='time')
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
        'keyword': args.keyword,
        'exactMatch': args.exact_match,
        'page': args.page,
        'pageSize': args.page_size,
        'order': args.order,
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
