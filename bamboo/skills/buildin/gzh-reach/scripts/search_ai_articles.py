#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# AI垂类——搜索公众号AI相关作品

按关键词搜索公众号作品，仅限 AI 垂直内容——专门收录 AI创作相关文章。搜索全部公众号文章请用「搜索关键词获取公众号作品（广域库）」接口。

**`POST`** `https://redfox.hk/story/api/parseWork/queryAiMsgs`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/parseWork/queryAiMsgs`

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
| keyword | String | 是 | 搜索关键词 | 人工智能 |
| pageNum | Integer | 是 | 页码 | 1 |
| pageSize | Integer | 是 | 每页条数 | 20 |
| startTime | String | 否 | start时间 | 2026-06-01 00:00:00 |
| endTime | String | 否 | 结束时间 | 2026-06-01 23:59:59 |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| code | Integer | 状态码（2000=成功） | 2000 |
| msg | String | 提示信息 | 成功 |
| data | Object | 返回数据 | — |
| list | Array | 数据列表 | — |
| authorId | String | authorID | 10000123456789 |
| commentCount | Integer | 评论数 | 280 |
| coverUrl | String | 封面链接 | https://example.com/cover.jpg |
| gmtCreate | String | 创建时间 | 2026-01-01 00:00:00 |
| gmtModified | String | 修改时间 | 2026-01-01 00:00:00 |
| likeCount | Integer | 点赞数 | 3500 |
| photoId | String | photoID | 10000123456789 |
| platform | Integer | platform | example |
| readCount | Integer | 阅读数 | 50000 |
| shareCount | Integer | 分享数 | 150 |
| title | String | 标题 | 人工智能热门课程 |
| topic | String | topic | — |
| type | String | 类型 | default |
| url | String | 链接地址 | https://example.com/example |
| userHeadUrl | String | userHead链接 | https://example.com/example |
| userName | String | user名称 | 示例用户 |
| pageNum | Integer | 页码 | 1 |
| pages | Integer | pages | 25 |
| pageSize | Integer | 每页条数 | 20 |
| total | Long | 总数 | 100 |

---

## 请求示例

```bash

```

---

## 响应示例

```json
{
  "code": 2000,
  "msg": "成功",
  "data": {
    "list": [
      "photoId": "10000123456789",
      "authorId": "10000123456789",
      "coverUrl": "https://example.com/cover.jpg",
      "userName": "示例用户",
      "userHeadUrl": "https://example.com/example",
      "title": "人工智能热门课程",
      "platform": example,
      "url": "https://example.com/example",
      "likeCount": 3500,
      "commentCount": 280,
      "shareCount": 150,
      "readCount": 50000,
      "type": "default",
      "topic": "示例值",
      "gmtCreate": "2026-01-01 00:00:00",
      "gmtModified": "2026-01-01 00:00:00"
    ],
    "total": 100,
    "pageNum": 1,
    "pageSize": 20,
    "pages": 25
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

SKILL_NAME = "gzh-reach"
API_URL = 'https://redfox.hk/story/api/parseWork/queryAiMsgs'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='AI垂类——搜索公众号AI相关作品')
    parser.add_argument('keyword')
    parser.add_argument('--page-num', type=int, default=1)
    parser.add_argument('--page-size', type=int, default=20)
    parser.add_argument('--start-time', default=None)
    parser.add_argument('--end-time', default=None)
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
        'pageNum': args.page_num,
        'pageSize': args.page_size,
        'startTime': args.start_time,
        'endTime': args.end_time,
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
