#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 获取哔哩哔哩账号作品列表 (优质库)

获取哔哩哔哩账号作品列表 (优质库)

**`POST`** `https://redfox.hk/story/api/bili/data/accountWorkList`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/bili/data/accountWorkList`

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
| mid | String | 否 | （非必填，与accountUrl二选一） | 946974 |
| accountUrl | String | 否 | （非必填，与mid二选一） | https://space.bilibili.com/946974?spm_id_from=333.788.upinfo.head.click |
| page | Integer | 否 |  （非必填，页码，默认1） | 1 |
| pageSize | Integer | 否 | （非必填，每页条数，默认10，最大50） | 10 |
| order | String | 否 | （非必填，排序：time=发布时间/play=播放数/like=点赞数，默认time） | time |

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
| mid | String | 账号MID | 946974 |
| page | Integer | 当前页码 | 1 |
| pageSize | Integer | 每页条数 | 10 |
| total | Integer | 总作品数（该账号下符合条件的作品总数） | 10 |
| workList | Array | 作品列表 | — |
| author | String | 作者昵称 | 影视飓风 |
| bvId | String | BV号 | BV1wE7P6bESL |
| coinCount | Integer | 投币数 | 79773 |
| commentCount | Integer | 评论数 | 8868 |
| crawlTime | String | 数据更新时间 | — |
| created | String | 发布时间 | 2026-06-22 17:00:00 |
| description | String | 视频描述 | 我们的1600万粉丝Q&A终于来了！… |
| duration | Integer | 时长（秒） | 1032 |
| favoriteCount | Integer | 收藏数 | 28345 |
| firstType | String | 一级分类 | 科技 |
| interactionQuantity | Integer | 互动数 | 348047 |
| likeCount | Integer | 点赞数 | 186730 |
| picUrl | String | 封面 | http://i0.hdslb.com/bfs/archive/1557911f2cecfc9aab972adad15e9a6c51ecd954.jpg |
| playCount | Integer | 播放数 | 1946284 |
| secondType | String | 二级分类 | 数码 |
| shareCount | Integer | 分享数 | 11207 |
| tagNames | Array | 作品标签名列表 | — |
| title | String | 作品标题 | 真开上机甲了？影视飓风1600万粉丝Q&A！ |
| videoReview | Integer | 弹幕数 | 33124 |

---

## 请求示例

```bash
请求参数：
{
  "mid": "946974",
  "accountUrl": "https://space.bilibili.com/946974?spm_id_from=333.788.upinfo.head.click",
  "page": 1,
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
    "mid": "946974",
    "page": 1,
    "pageSize": 10,
    "total": 10,
    "workList": [
      {
        "bvId": "BV1wE7P6bESL",
        "title": "真开上机甲了？影视飓风1600万粉丝Q&A！",
        "description": "我们的1600万粉丝Q&A终于来了！…",
        "duration": 1032,
        "picUrl": "http://i0.hdslb.com/bfs/archive/1557911f2cecfc9aab972adad15e9a6c51ecd954.jpg",
        "created": "2026-06-22 17:00:00",
        "author": "影视飓风",
        "firstType": "科技",
        "secondType": "数码",
        "playCount": 1946284,
        "likeCount": 186730,
        "favoriteCount": 28345,
        "commentCount": 8868,
        "shareCount": 11207,
        "videoReview": 33124,
        "coinCount": 79773,
        "interactionQuantity": 348047,
        "tagNames": [
          "科技猎手",
          "搞笑",
          "职场",
          "4K",
          "日常",
          "科技",
          "Q&A",
          "公司",
          "分享",
          "整活"
        ]
      }
    ]
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
API_URL = 'https://redfox.hk/story/api/bili/data/accountWorkList'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='获取哔哩哔哩账号作品列表 (优质库)')
    parser.add_argument('--mid', default=None)
    parser.add_argument('--account-url', default=None)
    parser.add_argument('--page', type=int, default=1)
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
        'mid': args.mid,
        'accountUrl': args.account_url,
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
