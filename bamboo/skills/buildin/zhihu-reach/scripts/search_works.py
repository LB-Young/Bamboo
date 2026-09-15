#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 知乎关键词搜索作品

**`POST`** `https://redfox.hk/story/api/zhihu/ability/searchWork`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/zhihu/ability/searchWork`

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
| offset | string | 是 | 翻页偏移量，+20递增，第一页为0，必填 | 0 |
| sort | string | 否 | 排序：upvoted_count 最多点赞；created_time 最新发布，非必填 | — |
| timeInterval | string | 否 | 时间范围：a_day 一天内；a_week 一周内；a_month 一个月内； three_months 3个月内；half_a_year 半年内；a_year 一年内，非必填 | — |
| vertical | string | 否 | 类型：answer 回答；article 文章；zvide 视频，非必填 | — |
| keword | string | 是 | 关键词，必填 | 未来 |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| isEnd | boolean | 是否结束 | — |
| nickname | string | 用户昵称 | — |
| opusId | string | 作品ID | — |
| publishTime | integer | 发布时间（时间戳） | — |
| title | string | 标题 | — |
| uid | string | 用户UID | — |

---

## 请求示例

```bash

```

---

## 响应示例

```json
{
  "code": 2000,
  "data": [
    {
      "isEnd": false,
      "nickname": "龙头18868",
      "opusId": "2079493065765557351",
      "publishTime": 1788569782,
      "title": "你对未来的十大预言是什么？？",
      "uid": "18868-42"
    },
    {
      "isEnd": false,
      "nickname": "xian ren",
      "opusId": "2013611938886739384",
      "publishTime": 1772864314,
      "title": "中国<em>未来</em>会怎么样",
      "uid": "xian-ren-38-45"
    }
  ],
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

SKILL_NAME = 'zhihu-reach'
API_URL = 'https://redfox.hk/story/api/zhihu/ability/searchWork'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='知乎关键词搜索作品')
    parser.add_argument('keyword')
    parser.add_argument('--offset', default='0')
    parser.add_argument('--sort', default=None)
    parser.add_argument('--time-interval', default=None)
    parser.add_argument('--vertical', default=None)
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
        'keword': args.keyword,
        'offset': args.offset,
        'sort': args.sort,
        'timeInterval': args.time_interval,
        'vertical': args.vertical,
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
