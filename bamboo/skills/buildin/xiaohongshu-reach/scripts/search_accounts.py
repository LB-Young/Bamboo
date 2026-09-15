#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 搜索关键词获取小红书账号 (优质库)

用户信息

**`POST`** `https://redfox.hk/story/api/xhsUser/searchUser`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/xhsUser/searchUser`

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
| keyword | String | 是 | 关键词 | 赵露思 |
| offset | Integer | 否 | 偏移量，从0开始，每页+20 | 0 |
| sortType | String | 否 | 排序方式: _0: 默认（相关性排序）_2: 最新（按最近发文时间排序）_4: 最热（按红狐指数排序） | _0 |

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
| hasMore | Integer | hasMore | true |
| list | Array | 数据列表 | — |
| accountAvatar | String | 头像链接 | "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo30tn2atj1ke005oqno2b65ak0rde9gb0?imageView2/2/w/80/format/jpg |
| accountCollectes | Integer | 总收藏数 | 104137 |
| accountDesc | String | 账号简介 | 这里是小红书视频官方账号🎬\n关注我，看我重生逆袭计划！ |
| accountFans | Integer | 平台粉丝数 | 330558 |
| accountId | String | 账号平台展示id | 6712113999 |
| accountLikes | Integer | 总点赞数 | 429909 |
| accountName | String | 账号名 | 小红书视频号 |
| accountTotalWorks | Integer | 总作品数 | 44 |
| accountType | String | account类型 | 100 |
| city | String | 地域-市 | 北京 |
| province | String | 地域-省 | 北京 |
| verifyInfo | String | verifyInfo | — |
| total | Long | 总数 | 100 |

---

## 请求示例

```bash
curl -X POST "https://redfox.hk/story/api/xhsUser/searchUser"
  -H "Content-Type: application/json"
  -H "REDFOX_API_KEY: your_api_key"
  -d '{"keyword": "示例关键词", "offset": 0, "sortType": "default"}'
```

---

## 响应示例

```json
{
  "code": 2000,
  "msg": "成功",
  "data": {
    "total": 100,
    "hasMore": true,
    "list": [
      "accountName": "小红书视频号",
      "accountAvatar": "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo30tn2atj1ke005oqno2b65ak0rde9gb0?imageView2/2/w/80/format/jpg,
      "accountId": "6712113999",
      "accountDesc": "这里是小红书视频官方账号🎬\n关注我，看我重生逆袭计划！",
      "accountFans": 330558,
      "accountTotalWorks": 44,
      "accountLikes": 429909,
      "accountCollectes": 104137,
      "accountType": "100",
      "verifyInfo": "示例值",
      "lastCreateTime": "2026-01-01 00:00:00",
      "noteCountThirty": 100,
      "province": "北京",
      "city": "北京"
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

SKILL_NAME = 'xiaohongshu-reach'
API_URL = 'https://redfox.hk/story/api/xhsUser/searchUser'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='搜索关键词获取小红书账号 (优质库)')
    parser.add_argument('keyword')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--sort-type', default='_0')
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
        'offset': args.offset,
        'sortType': args.sort_type,
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
