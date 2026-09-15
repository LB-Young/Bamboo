#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# YouTube视频下载

YouTube视频下载

**`POST`** `https://redfox.hk/story/api/parseWork/videoDownload/youtube`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/parseWork/videoDownload/youtube`

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
| url | String | 是 | 视频链接 | https://www.youtube.com/watch?v=dQw4w9WgXcQ |

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
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "data": {
    "cover": "https://i.ytimg.com/vi_webp/dQw4w9WgXcQ/maxresdefault.webp",
    "desc": "Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)",
    "resources": [
      {
        "coverUrl": "https://i.ytimg.com/vi_webp/dQw4w9WgXcQ/maxresdefault.webp",
        "downloadUrl": "https://rr4---sn-bvvbaxivnuxq5uu-vgqz.googlevideo.com/videoplayback?expire=1787217679&ei=r3KGaqekCo6iir4Pivqb-Q0&ip=2600%3A1700%3A6270%3A1d70%3A21b1%3A1378%3A71d7%3A7ed&id=o-ACD7dVTglPg0K7m7Br51VDTEQPd9sjfZlfSQ-0znhfHV&itag=18&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=1329&met=1787196079%2C&mh=7c&mm=18%2C29&mn=sn-bvvbaxivnuxq5uu-vgqz%2Csn-vgqsknde&ms=aub%2Crdu&mv=m&mvi=4&pl=43&rms=aub%2Caub&initcwndbps=2001250&bui=AR3QkAlxyRpAchuyQNAU9SiYPSjxw608Kt3JeXor4SNK2p_mfdOKscZ_I3jkPFk3KsDR0-c7p9k_VnMR&spc=KBGBcqIMluprqygnygJyaUEmEt4nLFyNEltZXv6p2bLoPsWqnevWM6jSX4vwyr77fNTaGAwzziXs7yXW&vprv=1&svpuc=1&mime=video%2Fmp4&ns=c989Qkbp2WFSPM3TqNS-p3sX&rqh=1&cnr=14&ratebypass=yes&dur=213.089&lmt=1766960953317159&mt=1787195583&fvip=4&fexp=51565116%2C51946838%2C51973818&c=WEB_EMBEDDED_PLAYER&sefc=1&txp=5538534&n=CCwRDm-jXhfauA&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cbui%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Cns%2Crqh%2Ccnr%2Cratebypass%2Cdur%2Clmt&lsparams=cps%2Cmet%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRgIhALXSASAfrNt79FQpNlmBoYIW_WPxSEHhXGY89DRDyjcIAiEAti-eyJDqWUEroi1WrbKYZfXQJifKwyyzpplv4rip35A%3D&sig=AE0s2JYwRAIgL0NiKVlWBUsgH49SaDUPqGIfb_rql8T4PM5Ez-8-EfYCIFKc9_sFpb1ojhvHLmHuApnZnw8Km7D6VaENQO9wMO1x",
        "durationSeconds": 213,
        "type": "video"
      },
      {
        "coverUrl": "https://i.ytimg.com/vi_webp/dQw4w9WgXcQ/maxresdefault.webp",
        "downloadUrl": "https://rr4---sn-bvvbaxivnuxq5uu-vgqz.googlevideo.com/videoplayback?expire=1787217679&ei=r3KGaqekCo6iir4Pivqb-Q0&ip=2600%3A1700%3A6270%3A1d70%3A21b1%3A1378%3A71d7%3A7ed&id=o-ACD7dVTglPg0K7m7Br51VDTEQPd9sjfZlfSQ-0znhfHV&itag=140&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=1329&met=1787196079%2C&mh=7c&mm=18%2C29&mn=sn-bvvbaxivnuxq5uu-vgqz%2Csn-vgqsknde&ms=aub%2Crdu&mv=m&mvi=4&pl=43&rms=aub%2Caub&initcwndbps=2001250&bui=AR3QkAmCJsTgtXwKANTwzXSWB_NXS1ZWBMT4ZR9SHAl-mgLNaZBXebO4h78zOv0Wqw7zCXqUpP9cpiWS&spc=KBGBcqIPluprqygnygJyaUEmEt4nLFyNEltZXv6p2bLoPsWqnevWM6jSX4vwyr77fO7cag9Lzs3sdw&vprv=1&svpuc=1&mime=audio%2Fmp4&ns=SNxD0C9uo_yH-O02SIQCWpwX&rqh=1&gir=yes&clen=3449447&dur=213.089&lmt=1766955925572207&mt=1787195583&fvip=4&keepalive=yes&fexp=51565116%2C51946838%2C51973818&c=WEB_EMBEDDED_PLAYER&sefc=1&txp=5532534&n=DWhWI_rke7H4Bg&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cbui%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Cns%2Crqh%2Cgir%2Cclen%2Cdur%2Clmt&lsparams=cps%2Cmet%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRgIhALXSASAfrNt79FQpNlmBoYIW_WPxSEHhXGY89DRDyjcIAiEAti-eyJDqWUEroi1WrbKYZfXQJifKwyyzpplv4rip35A%3D&sig=AE0s2JYwRQIhAJCrqgfb3DCeROvBzjVfUAApfj0k_RP-phT3gh29vPRIAiATrSwzVpM0JjtmxA2Bv__ltUgk7-68fh-N4NUq7hZfUw%3D%3D",
        "durationSeconds": 213,
        "type": "audio"
      }
    ],
    "title": "",
    "videoUrl": "https://rr4---sn-bvvbaxivnuxq5uu-vgqz.googlevideo.com/videoplayback?expire=1787217679&ei=r3KGaqekCo6iir4Pivqb-Q0&ip=2600%3A1700%3A6270%3A1d70%3A21b1%3A1378%3A71d7%3A7ed&id=o-ACD7dVTglPg0K7m7Br51VDTEQPd9sjfZlfSQ-0znhfHV&itag=18&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=1329&met=1787196079%2C&mh=7c&mm=18%2C29&mn=sn-bvvbaxivnuxq5uu-vgqz%2Csn-vgqsknde&ms=aub%2Crdu&mv=m&mvi=4&pl=43&rms=aub%2Caub&initcwndbps=2001250&bui=AR3QkAlxyRpAchuyQNAU9SiYPSjxw608Kt3JeXor4SNK2p_mfdOKscZ_I3jkPFk3KsDR0-c7p9k_VnMR&spc=KBGBcqIMluprqygnygJyaUEmEt4nLFyNEltZXv6p2bLoPsWqnevWM6jSX4vwyr77fNTaGAwzziXs7yXW&vprv=1&svpuc=1&mime=video%2Fmp4&ns=c989Qkbp2WFSPM3TqNS-p3sX&rqh=1&cnr=14&ratebypass=yes&dur=213.089&lmt=1766960953317159&mt=1787195583&fvip=4&fexp=51565116%2C51946838%2C51973818&c=WEB_EMBEDDED_PLAYER&sefc=1&txp=5538534&n=CCwRDm-jXhfauA&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cbui%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Cns%2Crqh%2Ccnr%2Cratebypass%2Cdur%2Clmt&lsparams=cps%2Cmet%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRgIhALXSASAfrNt79FQpNlmBoYIW_WPxSEHhXGY89DRDyjcIAiEAti-eyJDqWUEroi1WrbKYZfXQJifKwyyzpplv4rip35A%3D&sig=AE0s2JYwRAIgL0NiKVlWBUsgH49SaDUPqGIfb_rql8T4PM5Ez-8-EfYCIFKc9_sFpb1ojhvHLmHuApnZnw8Km7D6VaENQO9wMO1x"
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

SKILL_NAME = 'youtube-reach'
API_URL = 'https://redfox.hk/story/api/parseWork/videoDownload/youtube'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='YouTube视频下载')
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
