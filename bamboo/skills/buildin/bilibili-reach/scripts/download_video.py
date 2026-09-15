#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 哔哩哔哩视频下载

哔哩哔哩视频下载

**`POST`** `https://redfox.hk/story/api/parseWork/videoDownload/bilibili`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/parseWork/videoDownload/bilibili`

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
| url | String | 是 | 视频链接 | https://www.bilibili.com/video/BV1AmSSBMEqo/ |

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
  "url": "https://www.bilibili.com/video/BV1AmSSBMEqo/"
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "data": {
    "cover": "http://i0.hdslb.com/bfs/archive/3db430c1f939f8d40930ce2258d2ceeacf09373c.jpg",
    "desc": "",
    "resources": [
      {
        "coverUrl": "http://i0.hdslb.com/bfs/archive/3db430c1f939f8d40930ce2258d2ceeacf09373c.jpg",
        "downloadUrl": "https://upos-sz-estgcos.bilivideo.com/upgcxcode/49/55/37303615549/37303615549-1-192.mp4?e=ig8euxZM2rNcNbR3nwdVhwdlhW43hwdVhoNvNC8BqJIzNbfq9rVEuxTEnE8L5F6VnEsSTx0vkX8fqJeYTj_lta53NCM=&platform=html5&gen=playurlv3&og=cos&nbs=1&oi=1782024106&trid=e79544ee742c4008981d61f9cb93fach&os=estgcos&mid=0&deadline=1784805121&uipk=5&upsig=b94110920ece979f750bfadf2a598a9e&uparams=e,platform,gen,og,nbs,oi,trid,os,mid,deadline,uipk&bvc=vod&nettype=0&bw=1522017&lrs=0&build=0&dl=0&f=h_0_0&agrr=1&buvid=&orderid=0,1",
        "durationSeconds": null,
        "type": "video"
      }
    ],
    "title": "晒晒我的春日校园",
    "videoUrl": "https://upos-sz-estgcos.bilivideo.com/upgcxcode/49/55/37303615549/37303615549-1-192.mp4?e=ig8euxZM2rNcNbR3nwdVhwdlhW43hwdVhoNvNC8BqJIzNbfq9rVEuxTEnE8L5F6VnEsSTx0vkX8fqJeYTj_lta53NCM=&platform=html5&gen=playurlv3&og=cos&nbs=1&oi=1782024106&trid=e79544ee742c4008981d61f9cb93fach&os=estgcos&mid=0&deadline=1784805121&uipk=5&upsig=b94110920ece979f750bfadf2a598a9e&uparams=e,platform,gen,og,nbs,oi,trid,os,mid,deadline,uipk&bvc=vod&nettype=0&bw=1522017&lrs=0&build=0&dl=0&f=h_0_0&agrr=1&buvid=&orderid=0,1"
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

SKILL_NAME = 'bilibili-reach'
API_URL = 'https://redfox.hk/story/api/parseWork/videoDownload/bilibili'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='哔哩哔哩视频下载')
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
