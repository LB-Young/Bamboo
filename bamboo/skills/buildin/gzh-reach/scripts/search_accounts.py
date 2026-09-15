#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 搜索关键词获取公众号账号 (广域库)

通过关键词搜索微信公众号账号。

**`POST`** `https://redfox.hk/story/api/gzh/data/searchUser`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/gzh/data/searchUser`

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
| keyword | String | 是 | 搜索关键词 | 十点读书 |
| offset | Integer | 否 | 偏移量，从0开始，每页+20 | 0 |

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
| account | String | 账号平台展示ID | duhaoshu |
| accountName | String | 账号名 | 十点读书 |
| avatarUrl | String | 头像链接 | http://wx.qlogo.cn/mmhead/Q3auHgzwzM7BmxMfFQA3ic4p0H3Syd79W0p8Z6RnA9WnHcTTNrfPxSw/ |
| bizInfo | String | 账号采集用ID | MjM5MDMyMzg2MA== |
| description | String | 账号简介 | 深夜十点，陪你读书，美好的生活。好书/故事/美文/电台/美学。 |
| qrcodeUrl | String | 账号二维码 | http://mp.weixin.qq.com/mp/qrcode?scene=10000005&size=102&__biz=MjM5MDMyMzg2MA==&mid=2655500434&idx=1&sn=745d84e2213248177f0ca4bfa8892708 |
| verifyInfo | String | 认证信息 | 微信认证：厦门十点文化传播有限公司 |
| wxId | String | 公众号原始ID | gh_5c7e8b7f586b |
| total | Integer | 搜索结果总数 | 941407 |

---

## 请求示例

```bash
请求参数：
{
  "keyword": "十点读书",
  "offset": 0
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "data": {
    "list": [
      {
        "account": "duhaoshu",
        "accountName": "十点读书",
        "avatarUrl": "http://wx.qlogo.cn/mmhead/Q3auHgzwzM7BmxMfFQA3ic4p0H3Syd79W0p8Z6RnA9WnHcTTNrfPxSw/",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "description": "深夜十点，陪你读书，美好的生活。好书/故事/美文/电台/美学。",
        "qrcodeUrl": "http://mp.weixin.qq.com/mp/qrcode?scene=10000005&size=102&__biz=MjM5MDMyMzg2MA==&mid=2655500434&idx=1&sn=745d84e2213248177f0ca4bfa8892708",
        "verifyInfo": "微信认证：厦门十点文化传播有限公司",
        "wxId": "gh_5c7e8b7f586b"
      },
      {
        "account": "sddsapp",
        "accountName": "十点读书APP",
        "avatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/Bfow1tCcthjwyJxPj4c1ZBLFClVml3NbyGL6OJTiasicD2O3DlnR7Bo5gnbPCX0YqY8VMIcX7ym6cxt7ncIHbnjA/0?wx_fmt=png",
        "bizInfo": "MzI4NTU3MjQ0NA==",
        "description": "我们读书，就不孤单。下载十点读书APP，海量好书离线免费听。",
        "qrcodeUrl": "http://mp.weixin.qq.com/mp/qrcode?scene=10000005&size=102&__biz=MzI4NTU3MjQ0NA==&mid=2247487386&idx=1&sn=046e24e97adcea447e6bb8b1cad0669e",
        "updateTime": "2026-06-01 15:26:31",
        "verifyInfo": "微信认证：厦门十点文化传播有限公司",
        "wxId": "gh_0e4f1b7fd4ed"
      },
      {
        "account": "gh_8e331bc719dd",
        "accountName": "十点读书室",
        "avatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/kXw7NQnEib0pxHI1I5iaMNicX3icyW7ic6x49JFQT6wKnRhbJhq1WA61tuow31GteeLU7YicfcNYEmbm3vdiaA7EbaBTg/0?wx_fmt=png",
        "bizInfo": "MzkxODI0OTc1NQ==",
        "description": "分享读书心得，分析社会时政，交流心理情感，创造美好生活。",
        "qrcodeUrl": null,
        "updateTime": "2026-03-23 15:12:42",
        "verifyInfo": null,
        "wxId": "gh_8e331bc719dd"
      },
      {
        "account": "gh_56b27b0d597e",
        "accountName": "十点读书了",
        "avatarUrl": null,
        "bizInfo": "MzE5OTE0MjAxNw==",
        "description": null,
        "qrcodeUrl": null,
        "updateTime": "2026-07-09 11:46:22",
        "verifyInfo": null,
        "wxId": "gh_56b27b0d597e"
      },
      {
        "account": "gh_20214251e71f",
        "accountName": "Amy十点读书",
        "avatarUrl": "http://mmbiz.qpic.cn/sz_mmbiz_png/vYJGev8KOsUVDcuUWRhVdPxgx09sbuajXOtgFqJOmhc8lhgtaEU5hAKice6Y0ibvzmU9w1gA3NgFUlIbgcEez13g/0?wx_fmt=png",
        "bizInfo": "Mzk0NjcyMjczMw==",
        "description": null,
        "qrcodeUrl": null,
        "updateTime": "2025-12-29 14:58:54",
        "verifyInfo": null,
        "wxId": "gh_20214251e71f"
      },
      {
        "account": "gh_46f1d567cdcb",
        "accountName": "十点读书368",
        "avatarUrl": null,
        "bizInfo": "Mzk0MDg2ODU2Ng==",
        "description": null,
        "qrcodeUrl": null,
        "updateTime": "2026-07-06 13:12:01",
        "verifyInfo": null,
        "wxId": "gh_368c681e3f0c"
      },
      {
        "account": "gh_98657d16168c",
        "accountName": "十点读书7680",
        "avatarUrl": null,
        "bizInfo": "MzYyMzE3NTY1Mw==",
        "description": null,
        "qrcodeUrl": null,
        "updateTime": "2026-03-04 13:07:09",
        "verifyInfo": null,
        "wxId": "gh_98657d16168c"
      },
      {
        "account": "gh_2d1411bf24db",
        "accountName": "阿菲十点读书",
        "avatarUrl": "http://mmbiz.qpic.cn/sz_mmbiz_png/NWgMvrPPfsM1YuRickNHkicEIIvicfu2xtuYibybOwbWIJxSGrmv43xmiaL8la9gt2sUDEeGicXcarSoLoSPvagdoJ6A/0?wx_fmt=png",
        "bizInfo": "MzkzMjY3MjA2NA==",
        "description": "读书，写作，关注个人成长，传播情感价值",
        "qrcodeUrl": null,
        "updateTime": "2026-04-20 15:05:45",
        "verifyInfo": null,
        "wxId": "gh_2d1411bf24db"
      },
      {
        "account": "gh_080e96539846",
        "accountName": "十点读书君儿",
        "avatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/fbWnpvfNObjROicicVAZPherP5uTCSm6deufs4vc8kvZsaV0PYZCvdDvtXG3Qv88whVQDXINI4xrjiasP9dMiaX1fw/0?wx_fmt=png",
        "bizInfo": "MzkyOTYyNTc4Ng==",
        "description": "每天读点书，读的是智慧，长的是见识。",
        "qrcodeUrl": null,
        "updateTime": "2025-08-22 16:46:44",
        "verifyInfo": null,
        "wxId": "gh_080e96539846"
      },
      {
        "account": "gh_b80f0fafff5d",
        "accountName": "二十点读书",
        "avatarUrl": "http://mmbiz.qpic.cn/sz_mmbiz_png/4I8fQqNeNajZwgJicsYxEgWJ7ibkJ8c9NibMibXxUZQmtibicUI8fT1iafzv523JNazBSHr3uwM2iaqsfYrZkqdNSiaawFg/0?wx_fmt=png",
        "bizInfo": "MzkzNTk1MzgyNQ==",
        "description": null,
        "qrcodeUrl": null,
        "updateTime": "2025-09-04 17:19:57",
        "verifyInfo": null,
        "wxId": "gh_b80f0fafff5d"
      },
      {
        "account": "gh_bbb6896a4ab6",
        "accountName": "十点读书小筑",
        "avatarUrl": null,
        "bizInfo": "MzYzODgwMzQ0OQ==",
        "description": null,
        "qrcodeUrl": null,
        "updateTime": "2026-03-12 10:45:10",
        "verifyInfo": null,
        "wxId": "gh_bbb6896a4ab6"
      },
      {
        "account": "gh_90fe38a265bc",
        "accountName": "山月十点读书",
        "avatarUrl": null,
        "bizInfo": "MzYyNTQ0NDIwOQ==",
        "description": null,
        "qrcodeUrl": null,
        "updateTime": "2026-03-16 14:02:07",
        "verifyInfo": null,
        "wxId": "gh_90fe38a265bc"
      },
      {
        "account": "bhplay",
        "accountName": "十点读书时间",
        "avatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/ruicuQMsE22SxR021aFOYtOfuj3qezDy9NtAQa8JzHgFLgcjZFRRg1lGkDhyyu3iblXQtXdsWQseibVEWsyibYGlAQ/0?wx_fmt=png",
        "bizInfo": "MzA4OTg0OTcwMQ==",
        "description": "每天陪你读书，与你一起成长！",
        "qrcodeUrl": "http://mp.weixin.qq.com/mp/qrcode?scene=10000005&size=102&__biz=MzA4OTg0OTcwMQ==&mid=2650250579&idx=1&sn=09b5ae16e5a6b8e8d502f38fef9cee0d",
        "updateTime": "2025-08-30 16:31:39",
        "verifyInfo": null,
        "wxId": "gh_3c1b29fad8c8"
      },
      {
        "account": "gh_933f131b772e",
        "accountName": "十点读书日记",
        "avatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/PeovDwCJMkiaQspgfJic5IJt5TcElGkOJKsMQrVibLsal3TxNFteQPqz1IsvrF6OyEAOaibic9VGia04SL3w4Bicgto2w/0?wx_fmt=png",
        "bizInfo": "MzUzODcyNTYzMA==",
        "description": "本公众号记录日常的读书和生活的点滴。分享一些有用的东西。",
        "qrcodeUrl": null,
        "updateTime": "2026-06-15 15:23:25",
        "verifyInfo": null,
        "wxId": "gh_933f131b772e"
      },
      {
        "account": "gh_433fe5c7c802",
        "accountName": "晚间十点读书",
        "avatarUrl": "http://mmbiz.qpic.cn/sz_mmbiz_png/zp2diaKzFS40Duk0BSrIldhHumbMB9GGn4yxbFJbmibru9ic3RpHhFDS2KsWoialJ9ia1I5VqyHtaGL8FqQCooiajCwQ/0?wx_fmt=png",
        "bizInfo": "MzE5ODEwMTQ4Ng==",
        "description": "拒绝无效阅读！我们专注 ​​提炼书中20%核心价值​​。",
        "qrcodeUrl": null,
        "updateTime": "2025-08-30 17:07:24",
        "verifyInfo": null,
        "wxId": "gh_433fe5c7c802"
      },
      {
        "account": "gh_4fa686fe0840",
        "accountName": "周末十点读书",
        "avatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/FWyaX7ujDpagm61O4FYP08gMr0m25UfLZ9AafLusZicPDIiabvWOe2HCIwMaiacicc3rCefB7iakEvnjDibmaDRaFhPA/0?wx_fmt=png",
        "bizInfo": "MzIyNjY0MTU5MQ==",
        "description": "这里有一群热爱读书的小伙伴，如果你想拥有几位高质量，积极正能量的书友，欢迎加入我们哦 活动地点：大连西安路民政街333号",
        "qrcodeUrl": "http://mp.weixin.qq.com/mp/qrcode?scene=10000005&size=102&__biz=MzIyNjY0MTU5MQ==&mid=2247484109&idx=3&sn=2d4e1e343dfe51b7e02fd9d33be75a46",
        "updateTime": "2025-08-18 15:53:33",
        "verifyInfo": null,
        "wxId": "gh_4fa686fe0840"
      },
      {
        "account": "gh_3ab4da021684",
        "accountName": "青铜十点读书",
        "avatarUrl": "http://mmbiz.qpic.cn/sz_mmbiz_png/WW4MpnMiamZp5FhBIxia9ey7H0VNuicHAWW9pv86iauNvXIkmB8ZAyyl7Lmw0DfVHDQnBsBQa8F0fcOMATiaLw4BpkA/0?wx_fmt=png",
        "bizInfo": "Mzk2NDg3NDU1OQ==",
        "description": null,
        "qrcodeUrl": null,
        "updateTime": "2025-08-24 16:45:51",
        "verifyInfo": null,
        "wxId": "gh_3ab4da021684"
      },
      {
        "account": "gh_cdc9497a69dc",
        "accountName": "早上十点读书",
        "avatarUrl": null,
        "bizInfo": "MzcwODExMjQ2NQ==",
        "description": null,
        "qrcodeUrl": null,
        "updateTime": "2026-06-09 13:08:51",
        "verifyInfo": null,
        "wxId": "gh_cdc9497a69dc"
      },
      {
        "account": "gh_c43631c3cf36",
        "accountName": "十点读书小屋",
        "avatarUrl": "http://mmbiz.qpic.cn/sz_mmbiz_png/KBbo9hD0FMptwrbq9Fpic8tmGFb7Zlsmibs5Hats1ibRMSmPoVGdGPmaBticR7bO6zHia4xfI3AeDYC0OSiaBe7Vgib4Q/0?wx_fmt=png",
        "bizInfo": "Mzg2MjcyMzUzNw==",
        "description": "",
        "qrcodeUrl": "http://mp.weixin.qq.com/mp/qrcode?scene=10000005&size=102&__biz=Mzg2MjcyMzUzNw==&mid=2247483929&idx=1&sn=6ef49832b6e10608d3253d35bd178fe1",
        "updateTime": "2026-07-20 15:14:38",
        "verifyInfo": null,
        "wxId": "gh_c43631c3cf36"
      },
      {
        "account": "gh_73b2d611fc38",
        "accountName": "星宇十点读书荟",
        "avatarUrl": "http://mmbiz.qpic.cn/sz_mmbiz_png/Sibgr1BOW5uC08QHAibruN4LwpDmxgnV2NCWgGut3ibtzbYTnRxPsAduMQBb29yFuUhwEW9fA72fqDnvOmwZxiaHKA/0?wx_fmt=png",
        "bizInfo": "MzkwOTY0NDU3OQ==",
        "description": "感谢关注",
        "qrcodeUrl": null,
        "updateTime": "2025-09-05 17:02:35",
        "verifyInfo": null,
        "wxId": "gh_73b2d611fc38"
      }
    ],
    "total": 941407
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
API_URL = 'https://redfox.hk/story/api/gzh/data/searchUser'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='搜索关键词获取公众号账号 (广域库)')
    parser.add_argument('keyword')
    parser.add_argument('--offset', type=int, default=0)
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
