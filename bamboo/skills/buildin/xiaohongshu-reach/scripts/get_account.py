#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 获取小红书账号信息  (优质库)

查询信息

**`POST`** `https://redfox.hk/story/api/xhsUser/queryAccountDetail`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/xhsUser/queryAccountDetail`

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
| accountId | String | 是 | 小红书号 | rosy1109 |
| userId | String | 否 | 用户ID（用户主页地址 https://www.xiaohongshu.com/user/profile/5a73c5fa4eacab4c4ccc9778中的5a73c5fa4eacab4c4ccc9778） | 5a73c5fa4eacab4c4ccc9778 |

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
| accountAvatar | String | 头像链接 | "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo30tn2atj1ke005oqno2b65ak0rde9gb0?imageView2/2/w/80/format/jpg |
| accountCollectes | Integer | 总收藏数 | 104137 |
| accountDesc | String | 账号简介 | 这里是小红书视频官方账号🎬\n关注我，看我重生逆袭计划！ |
| accountFans | Integer | 平台粉丝数 | 330558 |
| accountFollows | Integer | 关注数 | 469 |
| accountId | String | 账号平台展示id | 6712113999 |
| accountLikes | Integer | 总点赞数 | 429909 |
| accountName | String | 账号名 | 小红书视频号 |
| accountTotalWorks | Integer | 总作品数 | 44 |
| accountUpdateTime | String | 账号更新时间 | 2026-05-13 03:04:53 |
| age | Integer | 年龄 | 25 |
| city | String | 地域-市 | 北京 |
| gender | String | 性别 | 2   {"1": "女", "0": "男", "2": "未知"} |
| ipLocation | String | IP属地-省 | 北京 |
| province | String | 地域-省 | 北京 |
| userId | String | 主键 id | 6357c096000000001802aa80 |

---

## 请求示例

```bash
curl -X POST "https://redfox.hk/story/api/xhsUser/queryAccountDetail"
  -H "Content-Type: application/json"
  -H "REDFOX_API_KEY: your_api_key"
  -d '{"accountId": "6712113999", "userId": "6357c096000000001802aa80"}'
```

---

## 响应示例

```json
{
  "code": 2000,
  "msg": "成功",
  "data": {
    "accountName": "小红书视频号",
    "accountAvatar": "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo30tn2atj1ke005oqno2b65ak0rde9gb0?imageView2/2/w/80/format/jpg,
    "accountId": "6712113999",
    "userId": "6357c096000000001802aa80",
    "gender": "2   {"1": "女", "0": "男", "2": "未知"}",
    "province": "北京",
    "city": "北京",
    "ipLocation": "北京",
    "accountFans": 330558,
    "accountDesc": "这里是小红书视频官方账号🎬\n关注我，看我重生逆袭计划！",
    "accountTotalWorks": 44,
    "accountLikes": 429909,
    "accountCollectes": 104137,
    "accountUpdateTime": "2026-05-13 03:04:53",
    "accountFollows": 469,
    "age": 25
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
API_URL = 'https://redfox.hk/story/api/xhsUser/queryAccountDetail'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='获取小红书账号信息  (优质库)')
    parser.add_argument('account_id')
    parser.add_argument('--user-id', default=None)
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
        'userId': args.user_id,
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
