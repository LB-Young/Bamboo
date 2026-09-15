#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 获取哔哩哔哩作品内容详情 (优质库)

获取哔哩哔哩作品内容详情 (优质库)

**`POST`** `https://redfox.hk/story/api/bili/data/workDetail`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/bili/data/workDetail`

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
| bvId | String | 否 | BV号（非必填，与workUrl二选一） | BV1ghJg6hEWV |
| workUrl | String | 否 | 作品链接（非必填，与bvId二选一，支持 https://www.bilibili.com/video/BV1xxx 或 https://b23.tv/xxx 格式） | https://www.bilibili.com/video/BV1ghJg6hEWV/?spm_id_from=333.1007.tianma.1-1-1.click |

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
| author | String | 作者昵称 | 影视飓风 |
| authorId | String | 作者ID | 946974 |
| bvId | String | BV号 | BV1ghJg6hEWV |
| coinCount | Integer | 投币数 | 19138 |
| commentCount | Integer | 评论数 | 4950 |
| created | String | 发布时间 | 2026-06-15 20:00:00 |
| description | String | 视频描述 | 大疆的Pocket 4P终于来了！这次我们想和你一起看看…… |
| duration | Integer | 时长，单位：秒 | 762 |
| favoriteCount | Integer | 收藏数 | 13589 |
| firstType | String | 一级分类 | 科技 |
| interactionQuantity | Integer | 互动数 | 125413 |
| likeCount | Integer | 点赞数 | 66946 |
| missionId | Integer | 视频关联活动ID | 4064796 |
| picUrl | String | 封面图URL | http://i0.hdslb.com/bfs/archive/c17d5325015b38eaf777198e9dd7f82a443ec1d1.jpg |
| playCount | Integer | 播放数 | 1330732 |
| secondType | String | 二级分类 | 数码 |
| shareCount | Integer | 分享数 | 14863 |
| tags | Array | 作品标签列表 | — |
| title | String | 作品标题 | 大疆Pocket 4P，到底 Pro 在哪？ |
| titleWords | Array | 内容词云/标题分词 | — |
| videoReview | Integer | 弹幕数 | 5927 |

---

## 请求示例

```bash
请求参数：
{
  "bvId": "BV1ghJg6hEWV",
  "workUrl": "https://www.bilibili.com/video/BV1ghJg6hEWV/?spm_id_from=333.1007.tianma.1-1-1.click"
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "msg": "成功",
  "data": {
    "bvId": "BV1ghJg6hEWV",
    "title": "大疆Pocket 4P，到底 Pro 在哪？",
    "duration": 762,
    "created": "2026-06-15 20:00:00",
    "firstType": "科技",
    "secondType": "数码",
    "tags": [
      "科技猎手",
      "数码",
      "科技",
      "摄影",
      "Pocket 4P",
      "大疆",
      "摄像",
      "DJI",
      "摄影器材",
      "拍摄"
    ],
    "titleWords": [
      "大疆"
    ],
    "interactionQuantity": 125413,
    "likeCount": 66946,
    "favoriteCount": 13589,
    "commentCount": 4950,
    "shareCount": 14863,
    "playCount": 1330732,
    "videoReview": 5927,
    "coinCount": 19138,
    "missionId": 4064796,
    "authorId": "946974",
    "author": "影视飓风",
    "description": "大疆的Pocket 4P终于来了！这次我们想和你一起看看……",
    "picUrl": "http://i0.hdslb.com/bfs/archive/c17d5325015b38eaf777198e9dd7f82a443ec1d1.jpg"
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
API_URL = 'https://redfox.hk/story/api/bili/data/workDetail'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='获取哔哩哔哩作品内容详情 (优质库)')
    parser.add_argument('--bv-id', default=None)
    parser.add_argument('--work-url', default=None)
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
        'bvId': args.bv_id,
        'workUrl': args.work_url,
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
