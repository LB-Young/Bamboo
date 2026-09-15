#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 查询小红书账号作品列表（优质库）

查询作品信息

**`POST`** `https://redfox.hk/story/api/xhsUser/queryWorkList`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/xhsUser/queryWorkList`

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
| redId | String | 否 | 账号平台展示id（redId和userid至少传一个） | rosy1109 |
| userid | String | 否 | 账号主键id（redId和userid至少传一个） | 5a73c5fa4eacab4c4ccc9778 |
| offset | Integer | 否 | 偏移量，从0开始，每页+20 | 0 |
| sortType | String | 否 | 排序方式 _0: 默认（相关性排序） _2: 最新（按发布时间倒序） _4: 最热（按互动数倒序） | — |
| publishTimeStart | String | 否 | 发布时间起始（格式 yyyy-MM-dd） | 2026-07-01 00:00:00 |
| publishTimeEnd | String | 否 | 发布时间结束（格式 yyyy-MM-dd） | 2026-08-01 00:00:00 |

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
| accountNickname | String | 作者昵称 | 赵露思 |
| accountType | String | account类型 | 影视娱乐 |
| accountUserid | String | 作者小红书id | 5a73c5fa4eacab4c4ccc9778 |
| coverUrl | String | 图片地址 | http://sns-img-hw.xhscdn.net/1040g2sg322qb8aqums704a17jb2vl5ro3ulfoio?imageView2/2/w/1080/format/webp |
| workCollectedCount | Integer | 收藏数 | 36915 |
| workCommentsCount | Integer | 评论数 | 33962 |
| workDesc | String | 作品内容 | #可露丽风 |
| workId | String | 作品id | 6a5cd594000000001101bb38 |
| workLikedCount | Integer | 点赞数 | 405124 |
| workPublishTime | String | 发布时间 | 2026-07-19 21:48:04 |
| workSharedCount | Integer | 转发数 | 4622 |
| workTitle | String | 作品标题 | 🦖 |
| workType | String | 分类（视频/图文） | normal |
| workUrl | String | 作品链接 | https://www.xiaohongshu.com/explore/6a5cd594000000001101bb38 |
| total | Long | 总数 | 100 |

---

## 请求示例

```bash
curl -X POST "https://redfox.hk/story/api/xhsUser/queryWorkList"
  -H "Content-Type: application/json"
  -H "REDFOX_API_KEY: your_api_key"
  -d '{"redId": "10000123456789", "userid": "10000123456789", "offset": 0, "sortType": "default", "publishTimeStart": "2026-01-01 00:00:00", "publishTimeEnd": "2026-01-01 00:00:00"}'
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
      {
        "accountNickname": "赵露思",
        "accountType": "影视娱乐",
        "accountUserid": "5a73c5fa4eacab4c4ccc9778",
        "coverUrl": "http://sns-img-hw.xhscdn.net/1040g2sg322qb8aqums704a17jb2vl5ro3ulfoio?imageView2/2/w/1080/format/webp",
        "workCollectedCount": 36915,
        "workCommentsCount": 33962,
        "workDesc": "#可露丽风",
        "workId": "6a5cd594000000001101bb38",
        "workLikedCount": 405124,
        "workPublishTime": "2026-07-19 21:48:04",
        "workReadedCount": null,
        "workSharedCount": 4622,
        "workTitle": "🦖",
        "workType": "normal",
        "workUrl": "https://www.xiaohongshu.com/explore/6a5cd594000000001101bb38"
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

SKILL_NAME = 'xiaohongshu-reach'
API_URL = 'https://redfox.hk/story/api/xhsUser/queryWorkList'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='查询小红书账号作品列表（优质库）')
    parser.add_argument('--red-id', default=None)
    parser.add_argument('--userid', default=None)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--sort-type', default=None)
    parser.add_argument('--publish-time-start', default=None)
    parser.add_argument('--publish-time-end', default=None)
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
        'redId': args.red_id,
        'userid': args.userid,
        'offset': args.offset,
        'sortType': args.sort_type,
        'publishTimeStart': args.publish_time_start,
        'publishTimeEnd': args.publish_time_end,
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
