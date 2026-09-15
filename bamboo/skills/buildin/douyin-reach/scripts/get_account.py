#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

#  获取抖音账号信息  (优质库)

查询用户信息

**`POST`** `https://redfox.hk/story/api/dyData/queryUser`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/dyData/queryUser`

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
| accountId | String | 是 | 抖音账号id（支持unique_id、short_id、uid任一匹配查询） | dy_user123 |

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
| age | Integer | 年龄 | 25 |
| avatarUrl | String | 头像链接 | https://example.com/avatar.jpg |
| awemeCount | Integer | 作品数 | 200 |
| city | String | 城市 | 深圳 |
| country | String | 国家 | 中国 |
| crawlTime | String | 数据更新时间 | 2026-05-20 12:00:00 |
| displayId | String | 账号平台展示id（unique_id优先，备选short_id） | dy_user123 |
| followerCount | Integer | 粉丝数 | 100000 |
| gender | String | 性别 | 男 |
| ipLocation | String | IP归属地 | 广东 |
| nickname | String | 账号名 | 抖音用户昵称 |
| province | String | 省份 | 广东 |
| signature | String | 账号简介 | 这是抖音账号简介 |
| totalFavorited | Long | 总获赞数 | 5000000 |
| uid | String | 用户uid | 1234567890 |

---

## 请求示例

```bash
curl -X POST "https://redfox.hk/story/api/dyData/queryUser"
  -H "Content-Type: application/json"
  -H "REDFOX_API_KEY: your_api_key"
  -d '{"accountId": "dy_user123"}'
```

---

## 响应示例

```json
{
  "code": 2000,
  "msg": "成功",
  "data": {
    "nickname": "抖音用户昵称",
    "avatarUrl": "https://example.com/avatar.jpg",
    "signature": "这是抖音账号简介",
    "displayId": "dy_user123",
    "uid": "1234567890",
    "gender": "男",
    "age": 25,
    "country": "中国",
    "province": "广东",
    "city": "深圳",
    "ipLocation": "广东",
    "followerCount": 100000,
    "awemeCount": 200,
    "totalFavorited": 5000000,
    "crawlTime": "2026-05-20 12:00:00"
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

SKILL_NAME = 'douyin-reach'
API_URL = 'https://redfox.hk/story/api/dyData/queryUser'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='获取抖音账号信息  (优质库)')
    parser.add_argument('account_id')
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
        'accountId': args.account_id,
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
