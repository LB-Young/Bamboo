#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 搜索关键词获取抖音账号 (广域库)

抖音账号搜索

**`POST`** `https://redfox.hk/story/api/dy/data/searchAccount`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/dy/data/searchAccount`

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
| keyword | String | 是 | 搜索关键词（必填，匹配账号名） | 罗志祥 |
| pageNum | Integer | 否 | 页码（从1开始，默认1） | 1 |
| pageSize | Integer | 否 | 每页大小（默认10，最大50） | 10 |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| list | Array | 数据列表 | — |
| avatarUrl | String | 头像链接 | — |
| bio | String | 账号简介 | — |
| displayName | String | 账号名  | — |
| fansCount | Integer | 平台粉丝数 | — |
| favoritingCount | Integer | 喜欢数 | — |
| followCount | Integer | 关注数 | — |
| secureId | String | 账号采集用id  | — |
| shortId | String | 账号平台展示id-short | — |
| totalLikes | Integer | 总点赞数 | — |
| uniqueName | String | 账号平台展示id  | — |
| userId | String | 账号主键id | — |
| videoCount | Integer | 总发布作品数 | — |
| pageNum | Integer | 当前页码 | — |
| pageSize | Integer | 每页大小 | — |
| total | Integer | 总记录数 | — |

---

## 请求示例

```bash

```

---

## 响应示例

```json
{
  "code": 2000,
  "data": {
    "list": [
      {
        "avatarUrl": "https://p3-pc.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_54f8f45c2af49ae36a1e6fcfc0d2665c.jpeg?from=2956013662",
        "bio": "",
        "displayName": "罗志祥",
        "fansCount": 23053615,
        "favoritingCount": 0,
        "followCount": 2,
        "secureId": "MS4wLjABAAAA2jD45shuaphDnTULtCA3baR-xPXsD97pzSzgKAYwfss",
        "shortId": null,
        "totalFansCount": 24157021,
        "totalLikes": 466854555,
        "uniqueName": "ShowLoGNF",
        "userId": "76725372134",
        "videoCount": 686
      }
    ],
    "pageNum": 1,
    "pageSize": 10,
    "total": 342341
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
API_URL = 'https://redfox.hk/story/api/dy/data/searchAccount'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='搜索关键词获取抖音账号 (广域库)')
    parser.add_argument('keyword')
    parser.add_argument('--page-num', type=int, default=1)
    parser.add_argument('--page-size', type=int, default=10)
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
