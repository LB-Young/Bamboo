#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

#  搜索关键词获取小红书作品 (优质库)

文章信息

**`POST`** `https://redfox.hk/story/api/xhsUser/searchArticle`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/xhsUser/searchArticle`

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
| keyword | String | 是 | 关键词 | 美食 |
| offset | Integer | 否 | 偏移量，从0开始，每页+20 | 0 |
| sortType | String | 否 | 排序方式： _0: 默认（相关性排序）_2: 最新（按发布时间排序）_4: 最热（按互动数排序） | _0 |
| exactMatch | Boolean | 否 | 是否精准匹配（默认false）      * false: 模糊匹配，关键词分词后部分匹配即可召回      * true: 精准匹配，关键词作为完整短语必须包含在文章标题、摘要或作者中 | false |

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
| accountNickname | String | 作者昵称 | 大白萝不怪 |
| accountType | String | account类型 | 100 |
| accountUserid | String | 作者小红书id | 565b17dc0bf90c754d6615b4 |
| coverUrl | String | 图片地址 | https://sns-i10.rednotecdn.com/notes_pre_post/1040g3k031k6lpmg43q2043gri3bto5dk2u1p6eg?imageView2/2/w/576/format/webp/q/87%7CimageMogr2/strip&redImage/frame/0&ap=1&sc=PREVIEW&sign=b670a0755ba8943337e700df1b2f702d&t=6a05685d&src=A |
| workCollectedCount | Integer | 收藏数 | 175 |
| workCommentsCount | Integer | 评论数 | 45 |
| workDesc | String | 作品内容 | 做了十多年建筑设计 标准化设计是硬性要求\n难得自己当甲方 不想把设计模版套在自己的家\n自己的房子总算能随心所欲\n家里的布置随着时间调整 越住越舒适~\n以舒适健康为居 是我们理想中高智感的家\n\t\n特别满意我的开放式厨房 洗切炒一气呵成\n要说不满意 就是用水问题\n武汉自来水氯味重得吓人\n做饭都闻到异味 污染事件更是频发\n拖了很久决定装净水器\n闺蜜家装的RO反渗透净水器虽然过滤效果好\n但每次制水要产生大量废水\n在业主群里咨询 |
| workId | String | 作品id | 687df3a1000000000d0184a4 |
| workLikedCount | Integer | 点赞数 | 210 |
| workPublishTime | String | 发布时间 | 2025-07-21 17:09:42 |
| workSharedCount | Integer | 转发数 | 28 |
| workTitle | String | 作品标题 | 建筑师的选择｜厨下净水器终于装好了！ |
| workType | String | 分类（视频/图文） | 主要描述：视频 or 图文 等 {"normal": "normal", "video": "video"} |
| workUrl | String | 作品链接 | https://www.xiaohongshu.com/explore/687df3a1000000000d0184a4 |
| total | Long | 总数 | 100 |

---

## 请求示例

```bash
curl -X POST "https://redfox.hk/story/api/xhsUser/searchArticle"
  -H "Content-Type: application/json"
  -H "REDFOX_API_KEY: your_api_key"
  -d '{"keyword": "示例关键词", "offset": 0, "sortType": "_0"}'
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
      "workId": "687df3a1000000000d0184a4",
      "workTitle": "建筑师的选择｜厨下净水器终于装好了！",
      "workDesc": "做了十多年建筑设计 标准化设计是硬性要求\n难得自己当甲方 不想把设计模版套在自己的家\n自己的房子总算能随心所欲\n家里的布置随着时间调整 越住越舒适~\n以舒适健康为居 是我们理想中高智感的家\n\t\n特别满意我的开放式厨房 洗切炒一气呵成\n要说不满意 就是用水问题\n武汉自来水氯味重得吓人\n做饭都闻到异味 污染事件更是频发\n拖了很久决定装净水器\n闺蜜家装的RO反渗透净水器虽然过滤效果好\n但每次制水要产生大量废水\n在业主群里咨询",
      "coverUrl": "https://sns-i10.rednotecdn.com/notes_pre_post/1040g3k031k6lpmg43q2043gri3bto5dk2u1p6eg?imageView2/2/w/576/format/webp/q/87%7CimageMogr2/strip&redImage/frame/0&ap=1&sc=PREVIEW&sign=b670a0755ba8943337e700df1b2f702d&t=6a05685d&src=A",
      "workUrl": "https://www.xiaohongshu.com/explore/687df3a1000000000d0184a4",
      "workPublishTime": "2025-07-21 17:09:42",
      "accountNickname": "大白萝不怪",
      "accountUserid": "565b17dc0bf90c754d6615b4",
      "workLikedCount": 210,
      "workCommentsCount": 45,
      "workCollectedCount": 175,
      "workReadedCount": 980,
      "workSharedCount": 28,
      "workType": "主要描述：视频 or 图文 等 {"normal": "normal", "video": "video"}",
      "accountType": "100"
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
API_URL = 'https://redfox.hk/story/api/xhsUser/searchArticle'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='搜索关键词获取小红书作品 (优质库)')
    parser.add_argument('keyword')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--sort-type', default='_0')
    parser.add_argument('--exact-match', action='store_true')
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
        'exactMatch': args.exact_match,
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
