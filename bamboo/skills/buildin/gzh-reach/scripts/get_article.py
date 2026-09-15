#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 根据作品地址获取公众号作品（实时）

通过文章链接查询公众号文章详细内容。

**`POST`** `https://redfox.hk/story/api/gzh/ability/temp/article/content`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/gzh/ability/temp/article/content`

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
| articleUrl | String | 是 | 文章链接，必填 | https://mp.weixin.qq.com/s/i4pZP3kBuMnxr-1js8200w |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| code | Integer | 接口响应状态码，200表示成功 | 200 |
| msg | String | 接口响应的提示或错误信息 | 成功 |
| data | Object | 接口返回的主要数据内容 | — |
| accountDesc | String | 文章描述 | 科研无限，云接未来！ |
| accountId | String | 公众号微信号 | researchcloud01 |
| accountName | String | 公众号名称 | 科研云 |
| adStatus | Integer | 广告状态，0-非广告，1-广告 | 0 |
| articleContent | String | 文章正文内容 | 关于举办人工智能赋能科研... |
| articleSummary | String | 文章摘要 | 关于举办人工智能赋能科研... |
| articleTitle | String | 文章标题 | 人工智能热门课程 |
| articleUrl | String | 文章链接 | http://mp.weixin.qq.com/s?__biz=... |
| audioLink | String | 音频链接 | — |
| authorName | String | 作者名称 | 科研云 |
| avatarUrl | String | 公众号头像链接 | http://mmbiz.qpic.cn/... |
| bgmUrl | String | 背景音乐链接 | — |
| bizKey | String | 公众号业务密钥 | MzI4NTkzNTgyOA== |
| commentSegmentId | String | 分段评论ID | — |
| countryId | String | 国家ID | 156 |
| countryName | String | 国家名称 | 中国 |
| coverImageUrl | String | 封面图片链接 | https://mmbiz.qpic.cn/... |
| dataUpdateTime | Integer | 数据更新时间戳 | 1782721210424 |
| downloadState | Integer | 下载状态 | 1 |
| gifList | Array | GIF列表 | — |
| imageUrls | Array | 图片链接列表 | — |
| indexLink | String | 首页链接 | http://wx.qlogo.cn/... |
| mainCommentId | Integer | 主评论ID | 4522991706383859700 |
| messageId | String | 消息ID | 2247832039 |
| newCommentId | Integer | 新评论ID | 4522991706383859700 |
| originalAuthor | String | 原创作者 | — |
| originalFlag | Integer | 原创标识，1-原创，0-非原创 | 0 |
| originalUrl | String | 原始链接 | https://mp.weixin.qq.com/s?... |
| picList | Array | 图片详情列表 | — |
| imageHeight | Integer | 图片高度 | 270 |
| imageWidth | Integer | 图片宽度 | 1080 |
| picUrl | String | 图片链接 | https://mmbiz.qpic.cn/... |
| provinceName | String | 省份名称 | 北京 |
| publishDate | String | 文章发布时间 | 2026-05-19 17:39:46 |
| publishOrderNum | Integer | 发布顺序 | 0 |
| remark | String | 备注信息 | — |
| sourceLink | String | 来源链接 | — |
| tagList | Array | 标签列表 | — |
| topicList | Array | 话题列表 | — |
| albumId | String | 话题ID | — |
| albumName | String | 话题名称 | — |
| contentCount | Integer | 内容数量 | — |
| uniqueId | String | 文章唯一标识 | 3F4DE056583609162E0816FBE8C183A3 |
| videoLink | String | 视频链接 | — |
| videoPageInfoList | Array | 视频页面信息列表 | — |
| dramaInfo | Object | 剧集信息 | — |
| dramaVideoInfo | Object | 剧集视频信息 | — |
| mpVideoTransInfo | Array | 视频转码信息 | — |
| wechatId | String | 公众号原始ID | gh_92efa4e6779a |

---

## 请求示例

```bash
请求参数：
{
  "articleUrl": "https://mp.weixin.qq.com/s/i4pZP3kBuMnxr-1js8200w"
}
```

---

## 响应示例

```json
{
  "code": 200,
  "data": {
    "articleUrl": "http://mp.weixin.qq.com/s?__biz=...",
    "articleTitle": "人工智能热门课程",
    "articleContent": "关于举办人工智能赋能科研...",
    "articleSummary": "关于举办人工智能赋能科研...",
    "accountDesc": "科研无限，云接未来！",
    "publishDate": "2026-05-19 17:39:46",
    "messageId": "2247832039",
    "uniqueId": "3F4DE056583609162E0816FBE8C183A3",
    "publishOrderNum": 0,
    "originalFlag": 0,
    "remark": "",
    "wechatId": "gh_92efa4e6779a",
    "accountId": "researchcloud01",
    "accountName": "科研云",
    "authorName": "科研云",
    "avatarUrl": "http://mmbiz.qpic.cn/...",
    "bizKey": "MzI4NTkzNTgyOA==",
    "originalAuthor": "",
    "indexLink": "http://wx.qlogo.cn/...",
    "originalUrl": "https://mp.weixin.qq.com/s?...",
    "sourceLink": "",
    "coverImageUrl": "https://mmbiz.qpic.cn/...",
    "bgmUrl": "",
    "audioLink": "",
    "videoLink": "",
    "adStatus": 0,
    "picList": [
      {
        "imageWidth": 1080,
        "picUrl": "https://mmbiz.qpic.cn/...",
        "imageHeight": 270
      }
    ],
    "gifList": [],
    "imageUrls": [
      "https://mmbiz.qpic.cn/..."
    ],
    "mainCommentId": "4522991706383859700",
    "newCommentId": "4522991706383859700",
    "commentSegmentId": "",
    "countryId": "156",
    "countryName": "中国",
    "provinceName": "北京",
    "tagList": [],
    "topicList": [],
    "videoPageInfoList": [
      {
        "dramaInfo": {},
        "dramaVideoInfo": {},
        "mpVideoTransInfo": []
      }
    ],
    "dataUpdateTime": 1782721210424,
    "downloadState": 1
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
API_URL = 'https://redfox.hk/story/api/gzh/ability/temp/article/content'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='根据作品地址获取公众号作品（实时）')
    parser.add_argument('article_url')
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
        'articleUrl': args.article_url,
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
