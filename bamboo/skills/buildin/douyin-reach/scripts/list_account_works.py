#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 获取抖音账号作品列表 (广域库)

抖音按账号获取内容列表

**`POST`** `https://redfox.hk/story/api/dy/data/listWorkByAccount`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/dy/data/listWorkByAccount`

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
| userId | String | 否 | 账号主键id / uid（userId / uniqueName / shortId 三选一必填） | 3822358551859599 |
| uniqueName | String | 否 | 账号平台展示id（三选一必填） | luoyonghao |
| shortId | String | 否 | 账号平台展示id-short（三选一必填） | — |
| pageNum | Integer | 否 | 页码（从1开始，默认1） | 1 |
| pageSize | Integer | 否 | 每页大小（默认10，最大50） | 10 |
| startDate | String | 否 | 开始时间 | 2026-07-01 |
| endDate | String | 否 | 结束时间 | 2026-07-20 |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| list | Array | 数据列表 | — |
| authorAvatarUrl | String | 作者头像 | — |
| authorFansCount | String | 作者粉丝数 | — |
| authorName | String | 作者昵称 | — |
| authorSecUid | String | 作者sec_uid | — |
| authorShortId | String | 作者抖音short_id | — |
| authorUid | String | 作者id | — |
| authorUniqueId | String | 作者抖音unique_id | — |
| collectCount | Integer | 收藏数 | — |
| commentCount | Integer | 评论数 | — |
| content | String | 作品正文/描述  | — |
| coverUrl | String | 作品封面链接  | — |
| duration | Integer | 作品时长-毫秒  | — |
| imageUrlList | Array | 图片列表-图文作品 | — |
| likeCount | Integer | 点赞数  | — |
| opusUrl | String | 作品链接  | — |
| publishTime | String | 作品发布时间  | — |
| shareCount | Integer | 分享数 | — |
| tagList | Array | 话题列表  | — |
| tagId | String | 话题id | — |
| tagName | String | 话题名称 | — |
| videoId | String | 作品id  | — |
| videoType | String | 作品类型 ：0=普通视频, 68=图集, 63=直播录屏等 | — |
| pageNum | Integer | 当前页码 | — |
| pageSize | Integer | 每页大小 | — |
| total | Integer | 总记录数 | — |

---

## 请求示例

```bash
请求参数：
{
  "userId": "3822358551859599",
  "uniqueName": "luoyonghao",
  "pageNum": 1,
  "pageSize": 10
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
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 89,
        "commentCount": 85,
        "content": "无论有没有文化，都推荐小奇和张骏的播客：《有没有文化现象》。 \n@张骏 @脱口秀小奇",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/0905ee9f8ef0469583bdd3f24a692199~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=%2BwrL8p4daOsNux6uN95TWw%2FLQro%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072204413329A20C441D9E4877E092",
        "duration": 39253,
        "imageUrlList": [],
        "likeCount": 1199,
        "opusUrl": "https://www.iesdouyin.com/share/video/7663047997038644499",
        "publishTime": "2026-07-16 17:00:07",
        "shareCount": 59,
        "tagList": [],
        "videoId": "7663047997038644499",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 6984,
        "commentCount": 613,
        "content": "【正片】罗永浩的X字路口！一年一度装x大会 #罗永浩的精选 #视频播客扶持计划  @抖音精选官方账号",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/8a1618ad1e0842959afc8125e7c884e0~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=lIOZPWiFs5NFgOme9CzZeJ%2BTmmE%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072204413329A20C441D9E4877E092",
        "duration": 10983574,
        "imageUrlList": [],
        "likeCount": 16474,
        "opusUrl": "https://www.iesdouyin.com/share/video/7662616607201496330",
        "publishTime": "2026-07-15 17:22:43",
        "shareCount": 3329,
        "tagList": [
          {
            "tagId": "7578774248387250222",
            "tagName": "视频播客扶持计划"
          },
          {
            "tagId": "7538657181571237924",
            "tagName": "罗永浩的精选"
          }
        ],
        "videoId": "7662616607201496330",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 79,
        "commentCount": 116,
        "content": "小奇想象中张骏的生活：装气满满的一天。7月15日，记得来看这期《罗永浩的X字路口》。 \n#抖音精选  #罗永浩的精选  @抖音精选官方账号  #脱口秀",
        "coverUrl": "https://p9-pc-sign.douyinpic.com/tos-cn-i-dy/c142ad4a2fcd47f69ea48225d0ce39ba~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=C3Jy3uob%2BUkCSWenr%2FoNu54WTvI%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072204413329A20C441D9E4877E092",
        "duration": 20459,
        "imageUrlList": [],
        "likeCount": 1082,
        "opusUrl": "https://www.iesdouyin.com/share/video/7662361634068778286",
        "publishTime": "2026-07-15 11:00:00",
        "shareCount": 51,
        "tagList": [
          {
            "tagId": "7538657181571237924",
            "tagName": "罗永浩的精选"
          },
          {
            "tagId": "1568943621383170",
            "tagName": "抖音精选"
          },
          {
            "tagId": "1570355740748801",
            "tagName": "脱口秀"
          }
        ],
        "videoId": "7662361634068778286",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 380,
        "commentCount": 152,
        "content": "脱口秀圈公认最装的人，居然是他......7月15日，记得来看这期《罗永浩的X字路口》。 \n#抖音精选  #罗永浩的精选  @抖音精选官方账号  #脱口秀",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/8566b9e9af734d4e8327ab164b47028e~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=3dwBZs7AxKjwSVUxdKnTvbV9CT4%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072204413329A20C441D9E4877E092",
        "duration": 17003,
        "imageUrlList": [],
        "likeCount": 3267,
        "opusUrl": "https://www.iesdouyin.com/share/video/7662361126260215092",
        "publishTime": "2026-07-15 10:00:00",
        "shareCount": 147,
        "tagList": [
          {
            "tagId": "1570355740748801",
            "tagName": "脱口秀"
          },
          {
            "tagId": "1568943621383170",
            "tagName": "抖音精选"
          },
          {
            "tagId": "7538657181571237924",
            "tagName": "罗永浩的精选"
          }
        ],
        "videoId": "7662361126260215092",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 257,
        "commentCount": 77,
        "content": "一年一度装逼大赛：谁是最能装的人？7月15日，记得来看这期《罗永浩的X字路口》。 \n#抖音精选  #罗永浩的精选  @抖音精选官方账号  #脱口秀",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/4d4b7b08e2c94cbe87b7bd01ed0bc990~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=i8erZ2mxkCJZOYk6ElnRBsg3kMw%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072204413329A20C441D9E4877E092",
        "duration": 19414,
        "imageUrlList": [],
        "likeCount": 1878,
        "opusUrl": "https://www.iesdouyin.com/share/video/7662306734085508402",
        "publishTime": "2026-07-14 18:00:07",
        "shareCount": 544,
        "tagList": [
          {
            "tagId": "1568943621383170",
            "tagName": "抖音精选"
          },
          {
            "tagId": "7538657181571237924",
            "tagName": "罗永浩的精选"
          },
          {
            "tagId": "1570355740748801",
            "tagName": "脱口秀"
          }
        ],
        "videoId": "7662306734085508402",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 116,
        "commentCount": 43,
        "content": "高级装x犯小奇：披着中专外衣的张骏。7月15日，记得来看这期《罗永浩的X字路口》。 \n#抖音精选  #罗永浩的精选  @抖音精选官方账号  #脱口秀",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/ad059e0824c54efa918dc892132632ce~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=1BDSIJvCPt2CE4UPDZLOV4T70OM%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072204413329A20C441D9E4877E092",
        "duration": 37483,
        "imageUrlList": [],
        "likeCount": 1067,
        "opusUrl": "https://www.iesdouyin.com/share/video/7662274941349399834",
        "publishTime": "2026-07-14 15:00:12",
        "shareCount": 94,
        "tagList": [
          {
            "tagId": "1570355740748801",
            "tagName": "脱口秀"
          },
          {
            "tagId": "1568943621383170",
            "tagName": "抖音精选"
          },
          {
            "tagId": "7538657181571237924",
            "tagName": "罗永浩的精选"
          }
        ],
        "videoId": "7662274941349399834",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 36,
        "commentCount": 43,
        "content": "是什么，把小奇逼得当场发这么毒的毒誓？7月15日，记得来看这期《罗永浩的X字路口》。\n#抖音精选  #罗永浩的精选  @抖音精选官方账号  #脱口秀",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/64ad51260ab5457f8709c6a7556a980d~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=3voXJSsy2Fw0q4ipcQuZFcM0%2B6Q%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072204413329A20C441D9E4877E092",
        "duration": 32086,
        "imageUrlList": [],
        "likeCount": 579,
        "opusUrl": "https://www.iesdouyin.com/share/video/7662229347914370323",
        "publishTime": "2026-07-14 12:03:18",
        "shareCount": 11,
        "tagList": [
          {
            "tagId": "1568943621383170",
            "tagName": "抖音精选"
          },
          {
            "tagId": "7538657181571237924",
            "tagName": "罗永浩的精选"
          },
          {
            "tagId": "1570355740748801",
            "tagName": "脱口秀"
          }
        ],
        "videoId": "7662229347914370323",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 2190,
        "commentCount": 570,
        "content": "【正片】罗永浩的X字路口！如果可以，你会删除伴侣出轨的记忆吗 #抖音精选  #罗永浩的精选  @抖音精选官方账号",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/99880eb2bb574928be1f25eae8b029d3~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2099682000&x-signature=I4NHGWxYTztlX0W9F1SA%2FT4h%2Bg0%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=20260718050339C6057956A5DC98097622",
        "duration": 7929409,
        "imageUrlList": [],
        "likeCount": 5495,
        "opusUrl": "https://www.iesdouyin.com/share/video/7660775531671014708",
        "publishTime": "2026-07-10 14:55:32",
        "shareCount": 863,
        "tagList": [
          {
            "tagId": "1568943621383170",
            "tagName": "抖音精选"
          },
          {
            "tagId": "7538657181571237924",
            "tagName": "罗永浩的精选"
          }
        ],
        "videoId": "7660775531671014708",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:188:188.jpeg?from=2956013662",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 152,
        "commentCount": 151,
        "content": "老罗抽自己嘴巴竟然是这个原因......7月10日，别忘了收看这期《罗永浩的X字路口》。\n#抖音精选  #罗永浩的精选  @抖音精选官方账号",
        "coverUrl": "https://p9-pc-sign.douyinpic.com/image-cut-tos-priv/c248afd31abfcfcebe26aabf9fc2662f~tplv-dy-resize-origshort-autoq-75:330.jpeg?lk3s=138a59ce&x-expires=2099678400&x-signature=AaZtCXUzPDl2%2BdZc6UHp9VNXjlk%3D&from=327834062&s=PackSourceEnum_WEBPC_RELATED_AWEME&se=false&sc=cover&biz_tag=pcweb_cover&l=202607180457582CD2052FD43D51563B2C",
        "duration": 24043,
        "imageUrlList": [],
        "likeCount": 2277,
        "opusUrl": "https://www.iesdouyin.com/share/video/7660186261373734180",
        "publishTime": "2026-07-09 14:00:00",
        "shareCount": 211,
        "tagList": [
          {
            "tagId": "1568943621383170",
            "tagName": "抖音精选"
          },
          {
            "tagId": "7538657181571237924",
            "tagName": "罗永浩的精选"
          }
        ],
        "videoId": "7660186261373734180",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_326685675806f8e08b44e25e0b9dc3b5~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "罗永浩的十字路口",
        "authorSecUid": "MS4wLjABAAAAdYnizw-yHaCBKEeZugZp-kWwLCjvB8GW-iR0I3BdxmkdyKxQkCODEKwzMTvYQgB0",
        "authorShortId": "0",
        "authorUid": "3822358551859599",
        "authorUniqueId": "luoyonghao",
        "collectCount": 3220,
        "commentCount": 4338,
        "content": "伴侣出轨了，但你俩都不想分手......7月10日，记得来看这期《罗永浩的X字路口》。 \n#抖音精选  #罗永浩的精选  @抖音精选官方账号",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/d902a0a0948a4e329595255a302a855d~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2099592000&x-signature=%2B8fj%2FoULaO3JQv8RRao5IxvxTWM%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=202607170423198B968DFDF6245F3F13B1",
        "duration": 26966,
        "imageUrlList": [],
        "likeCount": 20124,
        "opusUrl": "https://www.iesdouyin.com/share/video/7660185834255043876",
        "publishTime": "2026-07-09 10:00:00",
        "shareCount": 10203,
        "tagList": [
          {
            "tagId": "1568943621383170",
            "tagName": "抖音精选"
          },
          {
            "tagId": "7538657181571237924",
            "tagName": "罗永浩的精选"
          }
        ],
        "videoId": "7660185834255043876",
        "videoType": "0"
      }
    ],
    "pageNum": 1,
    "pageSize": 10,
    "total": 183
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

SKILL_NAME = 'douyin-reach'
API_URL = 'https://redfox.hk/story/api/dy/data/listWorkByAccount'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='获取抖音账号作品列表 (广域库)')
    parser.add_argument('--user-id', default=None)
    parser.add_argument('--unique-name', default=None)
    parser.add_argument('--short-id', default=None)
    parser.add_argument('--page-num', type=int, default=1)
    parser.add_argument('--page-size', type=int, default=10)
    parser.add_argument('--start-date', default=None)
    parser.add_argument('--end-date', default=None)
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
        'userId': args.user_id,
        'uniqueName': args.unique_name,
        'shortId': args.short_id,
        'pageNum': args.page_num,
        'pageSize': args.page_size,
        'startDate': args.start_date,
        'endDate': args.end_date,
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
