#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 搜索关键词获取公众号作品 (广域库)

通过关键词搜索微信公众号文章，支持按默认/最新/最热排序。搜索范围包括文章标题、摘要和作者。

**`POST`** `https://redfox.hk/story/api/gzh/data/searchArticle`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/gzh/data/searchArticle`

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
| exactMatch | boolean | 否 | 是否精准匹配（默认false） false: 模糊匹配，关键词分词后部分匹配即可召回 true: 精准匹配，关键词作为完整短语必须包含在文章标题、摘要或作者中 | false |
| offset | Integer | 否 | 偏移量，从0开始，每页+20 | 0 |
| sortType | String | 否 | 排序方式，0: 默认，2: 最新，4: 最热 | 0 |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| code | Integer | 接口响应状态码，例如 2000 表示成功 | 2000 |
| msg | String | 接口响应的提示或错误信息 | 成功 |
| data | Object | 接口返回的主要数据内容 | — |
| list | Array | 搜索结果列表 | — |
| author | String | 账号昵称 | 科技日报 |
| authorAvatarUrl | String | 作者头像链接 | http://... |
| bizInfo | String | 公众号采集用ID | MjM5MjUzNTgzNg== |
| collectCount | Integer | 收藏数 | 50 |
| commentCount | Integer | 评论数 | 100 |
| content | String | 作品正文 | 文章正文HTML内容 |
| coverUrl | String | 作品封面链接 | http://... |
| isOriginal | Integer | 原创标识，1 为原创 | 1 |
| likeCount | Integer | 点赞数 | 500 |
| orderNum | Integer | 发文位置，0 为头条 | 0 |
| originalAuthor | String | 原创作者 | 原创作者 |
| publishTime | String | 发布时间 | 2026-07-20 |
| readCount | Integer | 阅读数 | 10000 |
| shareCount | Integer | 分享数 | 30 |
| sourceUrl | String | 阅读原文链接 | http://... |
| summary | String | 作品简介 | 文章摘要 |
| title | String | 作品标题 | 人工智能的未来 |
| watchCount | Integer | 在看数 | 200 |
| workUrl | String | 作品链接 | http://mp.weixin.qq.com/s?... |
| workUuid | String | 作品ID | abc123def456 |
| total | Integer | 搜索结果总数 | 200 |

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
    "total": 200,
    "list": [
      {
        "title": "人工智能的未来",
        "summary": "文章摘要",
        "content": "文章正文HTML内容",
        "workUrl": "http://mp.weixin.qq.com/s?...",
        "coverUrl": "http://...",
        "publishTime": "2026-07-20",
        "readCount": 10000,
        "likeCount": 500,
        "watchCount": 200,
        "author": "科技日报",
        "isOriginal": 1,
        "orderNum": 0,
        "commentCount": 100,
        "collectCount": 50,
        "shareCount": 30,
        "sourceUrl": "http://...",
        "syncTime": "2026-07-20",
        "originalAuthor": "原创作者",
        "authorAvatarUrl": "http://...",
        "bizInfo": "MjM5MjUzNTgzNg==",
        "workUuid": "abc123def456"
      }
    ]
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

SKILL_NAME = "gzh-reach"
API_URL = 'https://redfox.hk/story/api/gzh/data/searchArticle'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='搜索关键词获取公众号作品 (广域库)')
    parser.add_argument('keyword')
    parser.add_argument('--exact-match', action='store_true')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--sort-type', default='0')
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
