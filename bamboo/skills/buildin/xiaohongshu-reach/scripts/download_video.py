#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 小红书视频下载

小红书视频下载

**`POST`** `https://redfox.hk/story/api/parseWork/videoDownload/xhs`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/parseWork/videoDownload/xhs`

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
| url | String | 是 | 视频链接 | https://www.xiaohongshu.com/explore/6a3c7aa6000000001003e071?xsec_token=AB-U4vc8DJUJoY9w-ebP_DvuxgiSNYmx8n35V4zvPo__M=&xsec_source=pc_feed |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| cover | String | 封面地址 | — |
| desc | String | 内容 | — |
| resources | Array | 全部媒体资源列表（视频、音频、图片等） | — |
| coverUrl | String | 封面链接 | — |
| downloadUrl | String | 下载链接 | — |
| durationSeconds | Integer | 时长（秒） | — |
| type | String | 资源类型：video-视频, audio-音频, mp3-音频, image-图片 | — |
| title | String | 标题 | — |
| videoUrl | String | 视频下载地址 | — |

---

## 请求示例

```bash
请求参数：
{
  "url": "https://www.xiaohongshu.com/explore/6a3c7aa6000000001003e071?xsec_token=AB-U4vc8DJUJoY9w-ebP_DvuxgiSNYmx8n35V4zvPo__M=&xsec_source=pc_feed"
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "data": {
    "cover": null,
    "desc": "追星党速码！不用相机，一台苹果就能拍爱豆神图\n现场灯光杂乱、远景发糊、人脸过曝？一套参数全部解决\n调好原相机设置，山顶看台也能拍出近景高清大片，舞台氛围感直接拉满✨\n保姆级调机步骤放图文里，进场前提前设置好\n长按锁定曝光+适配焦段，唱跳抓拍不模糊，收音干净无杂音\n再也不用羡慕别人的演唱会高清返图！\n提问：你们看演唱会最头疼拍不清舞台还是收音差？\n收藏存好，下次看演出直接照搬参数～\n#数码大玩家[话题]# #苹果手机[话题]# #演唱会拍照[话题]# #iphone小技巧[话题]# #手机拍照[话题]# #iphone原相机[话题]# #苹果拍照[话题]# #站姐拍照[话题]# #一起聊数码[话题]##果粉[话题]##DC特邀供稿[话题]#",
    "resources": [
      {
        "coverUrl": null,
        "downloadUrl": "https://sns-img-hw.xhscdn.com/notes_pre_post/1040g3k0321qnkg8mn2005qgugl9gg800c6r1dr8?imageView2/2/w/0/format/jpg",
        "durationSeconds": null,
        "type": "image"
      },
      {
        "coverUrl": null,
        "downloadUrl": "https://sns-img-hw.xhscdn.com/notes_pre_post/1040g3k0321qnkg8mn20g5qgugl9gg800a3og648?imageView2/2/w/0/format/jpg",
        "durationSeconds": null,
        "type": "image"
      },
      {
        "coverUrl": null,
        "downloadUrl": "https://sns-img-hw.xhscdn.com/notes_pre_post/1040g3k0321qnkg8mn2105qgugl9gg800jmflc7o?imageView2/2/w/0/format/jpg",
        "durationSeconds": null,
        "type": "image"
      },
      {
        "coverUrl": null,
        "downloadUrl": "https://sns-img-hw.xhscdn.com/notes_pre_post/1040g3k0321qnkg8mn21g5qgugl9gg800fgmp4qo?imageView2/2/w/0/format/jpg",
        "durationSeconds": null,
        "type": "image"
      },
      {
        "coverUrl": null,
        "downloadUrl": "https://sns-img-hw.xhscdn.com/notes_pre_post/1040g3k0321qnkg8mn2205qgugl9gg8008s67v9g?imageView2/2/w/0/format/jpg",
        "durationSeconds": null,
        "type": "image"
      },
      {
        "coverUrl": null,
        "downloadUrl": "https://sns-img-hw.xhscdn.com/notes_pre_post/1040g3k0321qnkg8mn22g5qgugl9gg800cqmap7g?imageView2/2/w/0/format/jpg",
        "durationSeconds": null,
        "type": "image"
      }
    ],
    "title": "🔥iPhone隐藏演唱会拍摄模式｜原图直出高清",
    "videoUrl": null
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

SKILL_NAME = 'xiaohongshu-reach'
API_URL = 'https://redfox.hk/story/api/parseWork/videoDownload/xhs'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='小红书视频下载')
    parser.add_argument('url')
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
        'url': args.url,
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
