#!/usr/bin/env python3
"""
Official RedFoxHub API document for this script:

# 搜索关键词获取抖音作品 (广域库)

抖音按关键词搜索内容

**`POST`** `https://redfox.hk/story/api/dy/data/searchWork`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/dy/data/searchWork`

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
| keyword | String | 否 | 搜索关键词（必填，匹配作品正文） | 美食 |
| exactMatch | Boolean | 否 | 是否精准匹配（默认false） false: 模糊匹配，关键词分词后部分匹配即可召回 true: 精准匹配，关键词作为完整短语必须包含在作品标题或作者中 | — |
| startDate | String | 否 | 开始日期（可选，格式：yyyy-MM-dd） | 2026-01-01 |
| endDate | String | 否 | 结束日期（可选，格式：yyyy-MM-dd） | 2026-07-21 |
| pageNum | Integer | 否 | 页码（从1开始，默认1） | 1 |
| pageSize | Integer | 否 | 每页大小（默认10，最大50） | 10 |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| list | Array | 数据列表 | — |
| authorAvatarUrl | String | 作者头像 | — |
| authorName | String | 作者昵称 | — |
| authorSecUid | String | 作者sec_uid | — |
| authorShortId | String | 作者抖音short_id | — |
| authorUid | String | 作者id | — |
| authorUniqueId | String | 作者抖音unique_id | — |
| collectCount | Integer | 收藏数 | — |
| commentCount | Integer | 评论数 | — |
| content | String | 作品正文/描述 | — |
| coverUrl | String | 作品封面链接 | — |
| duration | Integer | 作品时长-毫秒 | — |
| imageUrlList | Array | 图片列表-图文作品 | — |
| likeCount | Integer | 点赞数 | — |
| opusUrl | String | 作品链接 | — |
| publishTime | String | 作品发布时间 | — |
| shareCount | Integer | 分享数 | — |
| tagList | Array | 话题列表 | — |
| tagId | String | 话题id | — |
| tagName | String | 话题名称 | — |
| videoId | String | 作品id | — |
| videoType | String | 作品类型：0=普通视频, 68=图集, 63=直播录屏等 | — |
| pageNum | Integer | 当前页码 | — |
| pageSize | Integer | 每页大小 | — |
| total | Integer | 总记录数 | — |

---

## 请求示例

```bash
请求参数：
{
  "keyword": "美食",
  "startDate": "2026-01-01",
  "endDate": "2026-07-21",
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
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_e4f033c2d1a68344bb51a74b679bcd72~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "四羊",
        "authorSecUid": "MS4wLjABAAAA_6Nd0FVeJf0XTtrO8z5cJYKnoDthUVcOrrlj15VxJyAibmohiypHqhQ800JcoDN6",
        "authorShortId": "0",
        "authorUid": "2814369113837228",
        "authorUniqueId": "ssssyyyy0316",
        "collectCount": 1790444,
        "commentCount": 1363122,
        "content": " 挑战让82岁语文老师写高考作文，还有一场谋划了很久的惊喜行动 #四羊 #美的全屋智能#一声小美生活更美 #人间观察计划 #在拍一种很新的vlog #普通而珍贵的她 #抖音里的人",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/9791ff05f6164dfe9863bb26d1ed3fba~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=YdOQK7LiVuZ5S%2B6noSyf3ryZNBY%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072204404299F008A853253F810BA9",
        "duration": 354639,
        "imageUrlList": [],
        "likeCount": 21649714,
        "opusUrl": "https://www.iesdouyin.com/share/video/7599153358661799206",
        "publishTime": "2026-01-25 17:01:22",
        "shareCount": 5090271,
        "tagList": [
          {
            "tagId": "1656985640099843",
            "tagName": "四羊"
          },
          {
            "tagId": "1675440274428942",
            "tagName": "美的全屋智能"
          },
          {
            "tagId": "7576613780038092836",
            "tagName": "一声小美生活更美"
          },
          {
            "tagId": "1638697128713219",
            "tagName": "人间观察计划"
          },
          {
            "tagId": "1757627772683267",
            "tagName": "在拍一种很新的vlog"
          },
          {
            "tagId": "7612594283526227994",
            "tagName": "普通而珍贵的她"
          },
          {
            "tagId": "1599351921607684",
            "tagName": "抖音里的人"
          }
        ],
        "videoId": "7599153358661799206",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_21b4383e542b8991bcd33d33eeda7d8d.jpeg?from=327834062",
        "authorName": "人民日报",
        "authorSecUid": "MS4wLjABAAAA8U_l6rBzmy7bcy6xOJel4v0RzoR_wfAubGPeJimN__4",
        "authorShortId": "0",
        "authorUid": "104255897823",
        "authorUniqueId": "rmrbxmt",
        "collectCount": 836953,
        "commentCount": 340908,
        "content": "绝美一幕！当高铁驶入“千里江山图”……@貔貅摄影📸",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/image-cut-tos-priv/d9ae093ac7312f447560c7765775bc9b~tplv-dy-resize-origshort-autoq-75:330.jpeg?lk3s=138a59ce&x-expires=2095797600&x-signature=6T%2FetlqLuYjzDAoeWhez40%2B%2BoD8%3D&from=327834062&s=PackSourceEnum_WEBPC_RELATED_AWEME&se=false&sc=cover&biz_tag=pcweb_cover&l=20260603064702B390C102BF4A5C350C5D",
        "duration": 22334,
        "imageUrlList": [],
        "likeCount": 11292941,
        "opusUrl": "https://www.iesdouyin.com/share/video/7614341586570300691",
        "publishTime": "2026-03-07 10:54:57",
        "shareCount": 3295673,
        "tagList": [],
        "videoId": "7614341586570300691",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p26.douyinpic.com/aweme/100x100/aweme-avatar/douyin-user-private-image_lilanxin.369_d52b51cfd28cc8f1c29475433710b182405f5202bf22519b9d07b717065fcc32.jpeg?from=327834062",
        "authorName": "新华社",
        "authorSecUid": "MS4wLjABAAAAxA44mxJVod_Aq5wc0cZrbZHJ2S_DnoJctGpb_mOvsxs",
        "authorShortId": "0",
        "authorUid": "93288642596",
        "authorUniqueId": "xinhuashe",
        "collectCount": 1123710,
        "commentCount": 477040,
        "content": "完整版来了！习近平为美国总统特朗普举行欢迎仪式#近镜头",
        "coverUrl": "https://p26-sign.douyinpic.com/tos-cn-i-dy/f07ac2a7ad7f4e3d98444ee24d3884d7~noop.webp?lk3s=138a59ce&x-expires=1785268800&x-signature=TmDRNP99EtoqeNx5wOYclfeyijo%3D&from=327834062_large&s=PackSourceEnum_CHALLENGE_AWEME&se=false&sc=cover&biz_tag=aweme_video&l=202607150428308200C487F94CBC34D4E9",
        "duration": 1131488,
        "imageUrlList": [],
        "likeCount": 9220564,
        "opusUrl": "https://www.iesdouyin.com/share/video/7639577678311443775",
        "publishTime": "2026-05-14 11:03:14",
        "shareCount": 2386755,
        "tagList": [
          {
            "tagId": "1598706004484100",
            "tagName": "近镜头"
          }
        ],
        "videoId": "7639577678311443775",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_5bee97f2a0e75e704bb03d4135e81cfe~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "Ryan_📸",
        "authorSecUid": "MS4wLjABAAAAz6AKIlNv0N8p9VTIp3BmzFSdMe0AU4j83QB7gyV43g8",
        "authorShortId": "0",
        "authorUid": "102541088406",
        "authorUniqueId": "Ryan845745004",
        "collectCount": 351088,
        "commentCount": 58717,
        "content": "我被视觉（中国）拒签了 呜呜～ #风光摄影 #尼康 #抖音摄影美学大赏 #青年创作者成长计划 #inmyfeelings",
        "coverUrl": "https://p9-pc-sign.douyinpic.com/tos-cn-i-dy/cb898b7eaa924b89b2d35d9025026cf3~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100038400&x-signature=zumUmYLEBgI9l2sXI2H9qcDgAZk%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=2026072208152059544CC5FAD0E77C277E",
        "duration": 23914,
        "imageUrlList": [],
        "likeCount": 9219176,
        "opusUrl": "https://www.iesdouyin.com/share/video/7625880191402773823",
        "publishTime": "2026-04-07 13:10:00",
        "shareCount": 490524,
        "tagList": [
          {
            "tagId": "1606973738716174",
            "tagName": "inmyfeelings"
          },
          {
            "tagId": "1596315994195976",
            "tagName": "风光摄影"
          },
          {
            "tagId": "1632381879015428",
            "tagName": "尼康"
          },
          {
            "tagId": "7363130335623645211",
            "tagName": "抖音摄影美学大赏"
          },
          {
            "tagId": "7529832653680281615",
            "tagName": "青年创作者成长计划"
          }
        ],
        "videoId": "7625880191402773823",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3.douyinpic.com/aweme-avatar/tos-cn-avt-0015_c85c768ddc337c2a2b06274bda68611a~tplv-dy-shrink:188:188.jpeg?from=2956013662",
        "authorName": "榛子Bel canto🎼",
        "authorSecUid": "MS4wLjABAAAAnPd92LfTcUAd7nwp9WdYBkIlKbvwQMzutwSgV7X5iQQ",
        "authorShortId": "0",
        "authorUid": "644760193474891",
        "authorUniqueId": "52623385786",
        "collectCount": 225273,
        "commentCount": 31807,
        "content": "来这里怎么能不唱#长沙 #橘子洲头 #怀念故人 #美声",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/image-cut-tos-priv/55132cfd34a9c11100df57bdceed523a~tplv-dy-resize-origshort-autoq-75:330.jpeg?lk3s=138a59ce&x-expires=2100056400&x-signature=ZAEvCNnKWINQtLBDfvfXAxnORPs%3D&from=327834062&s=PackSourceEnum_WEBPC_RELATED_AWEME&se=false&sc=cover&biz_tag=pcweb_cover&l=202607221316529796CC2316DFF76D6A3C",
        "duration": 21300,
        "imageUrlList": [],
        "likeCount": 8254949,
        "opusUrl": "https://www.iesdouyin.com/share/video/7645899644263118821",
        "publishTime": "2026-05-31 11:55:36",
        "shareCount": 812738,
        "tagList": [
          {
            "tagId": "1575252441675790",
            "tagName": "美声"
          },
          {
            "tagId": "1764938135648269",
            "tagName": "长沙"
          },
          {
            "tagId": "1580524258237454",
            "tagName": "橘子洲头"
          },
          {
            "tagId": "1594905921268739",
            "tagName": "怀念故人"
          }
        ],
        "videoId": "7645899644263118821",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p26.douyinpic.com/aweme-avatar/tos-cn-avt-0015_21b4383e542b8991bcd33d33eeda7d8d~tplv-dy-shrink:188:188.jpeg?from=2956013662",
        "authorName": "人民日报",
        "authorSecUid": "MS4wLjABAAAA8U_l6rBzmy7bcy6xOJel4v0RzoR_wfAubGPeJimN__4",
        "authorShortId": "0",
        "authorUid": "104255897823",
        "authorUniqueId": "rmrbxmt",
        "collectCount": 278013,
        "commentCount": 117,
        "content": "美国总统特朗普：习主席是一个很温暖的人，完全是实干家，不空谈、不玩虚的。特朗普还高度评价欢迎仪式上的中国人民解放军仪仗队表现。",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/dc49dd5d7d504b5bb5d31f3faac78ffe~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2094825600&x-signature=Zo4%2BLf4n%2FjK7r4mjML8kCi8rRXk%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=202605230029290933E17F845818D62868",
        "duration": 22507,
        "imageUrlList": [],
        "likeCount": 7539594,
        "opusUrl": "https://www.iesdouyin.com/share/video/7640009263628176694",
        "publishTime": "2026-05-15 14:58:02",
        "shareCount": 862450,
        "tagList": [],
        "videoId": "7640009263628176694",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-i-0813c001_o4yAmC8QLAfkcPs0eQI52CAVAfIeXMDAMaBar9~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "七月🐒",
        "authorSecUid": "MS4wLjABAAAA0i44oyituOKp0wDJqeKsP2EYOl4QShNdaoIol5oxpww",
        "authorShortId": "0",
        "authorUid": "87847635659",
        "authorUniqueId": "Jul_Jin",
        "collectCount": 411330,
        "commentCount": 72719,
        "content": "我没有被视觉中国拒签‼️可以看看我镜头下的中式美学吗🙏 #青年创作者成长计划 #抖音摄影美学大赏 #中式美学 #风光摄影 #我的摄影作品",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-0813c000-ce/o0AeILHwAeo7mGdyg4AJpGAoNfIBuTTOgAFxQI~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100027600&x-signature=Z6ZQqunV4fyXb%2FpJqWIViOQEOoc%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=202607220517568409F59D4EB5E76CF56D",
        "duration": 35605,
        "imageUrlList": [],
        "likeCount": 7410678,
        "opusUrl": "https://www.iesdouyin.com/share/video/7628043288460846961",
        "publishTime": "2026-04-13 09:03:49",
        "shareCount": 1087215,
        "tagList": [
          {
            "tagId": "1596315994195976",
            "tagName": "风光摄影"
          },
          {
            "tagId": "7529832653680281615",
            "tagName": "青年创作者成长计划"
          },
          {
            "tagId": "7363130335623645211",
            "tagName": "抖音摄影美学大赏"
          },
          {
            "tagId": "1608784992273416",
            "tagName": "中式美学"
          },
          {
            "tagId": "1593491890908164",
            "tagName": "我的摄影作品"
          }
        ],
        "videoId": "7628043288460846961",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3-pc.douyinpic.com/aweme-avatar/tos-cn-avt-0015_b9a7c37ed2aa6694d93d02c6d9cab3cf~tplv-dy-shrink:96:96.jpeg?from=327834062",
        "authorName": "爱黏人的圆子哔___",
        "authorSecUid": "MS4wLjABAAAAMZtNQgLD-D1MiK8v0MFkdLnrCrNShu73ZD4F5TPOROHR_EVwR9anALfOr4pFOh5D",
        "authorShortId": "0",
        "authorUid": "3408138689846743",
        "authorUniqueId": "sunnycoco9999",
        "collectCount": 2249432,
        "commentCount": 136113,
        "content": "无公司，无投资，无AI！我们手搓了一个原创中恐无限流大电影！？ \n为爱发电作品，从两年前就开始策划啦，谢谢大家的观看！\n希望可以通过这个作品宣传昆曲非遗文化，用无限流的方式打开昆曲之美～\n#吉时已到 #无限流 #昆曲",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/6c8a8c4634644d778578ff44adfb46b8~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=I7LOpgugh80Wslg89b3fKrFcfTg%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=20260722044253C2C6E2F75450BA75EA04",
        "duration": 5767638,
        "imageUrlList": [],
        "likeCount": 6762685,
        "opusUrl": "https://www.iesdouyin.com/share/video/7632278899262573862",
        "publishTime": "2026-04-24 19:00:14",
        "shareCount": 4230886,
        "tagList": [
          {
            "tagId": "1575470415517710",
            "tagName": "昆曲"
          },
          {
            "tagId": "1606517758497806",
            "tagName": "吉时已到"
          }
        ],
        "videoId": "7632278899262573862",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p26.douyinpic.com/aweme-avatar/tos-cn-avt-0015_fff15ab3be07872e7ee44dfd748eac9c~tplv-dy-shrink:188:188.jpeg?from=2956013662",
        "authorName": "小白小磊小天才",
        "authorSecUid": "MS4wLjABAAAAndXGQV8AQMSUl8cLN7kI4g_pByvV2HqGHnbBcWjCcE1OiUdIxZwCvInyzXQzcTH7",
        "authorShortId": "0",
        "authorUid": "4283319422041224",
        "authorUniqueId": "LLbaby0314",
        "collectCount": 463154,
        "commentCount": 155444,
        "content": "美食博主手搓超越AI的一年🍳🍎🍴 人不能输❕人怎么可能输❕#酸奶碗 #冰糖葫芦 #美术生 #当季新菜单挑战赛 #美食博主",
        "coverUrl": "https://p3-pc-sign.douyinpic.com/tos-cn-i-dy/e4e7c5ccf93b49bfaf2719e55a5927e3~tplv-dy-cropcenter:323:430.jpeg?lk3s=138a59ce&x-expires=2100024000&x-signature=xZwJHG%2BCB1VdmR6KllC3%2FWNz%2B0k%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=true&sh=323_430&sc=cover&biz_tag=pcweb_cover&l=202607220444544A423751C2F45D6B4E5F",
        "duration": 32716,
        "imageUrlList": [],
        "likeCount": 6744069,
        "opusUrl": "https://www.iesdouyin.com/share/video/7590982287953497378",
        "publishTime": "2026-01-03 12:08:33",
        "shareCount": 3250696,
        "tagList": [
          {
            "tagId": "1576515209030670",
            "tagName": "美术生"
          },
          {
            "tagId": "1637863718285323",
            "tagName": "酸奶碗"
          },
          {
            "tagId": "1576684145717278",
            "tagName": "冰糖葫芦"
          },
          {
            "tagId": "7566214863073052715",
            "tagName": "当季新菜单挑战赛"
          },
          {
            "tagId": "1576698555072542",
            "tagName": "美食博主"
          }
        ],
        "videoId": "7590982287953497378",
        "videoType": "0"
      },
      {
        "authorAvatarUrl": "https://p3.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_9984ee99cd876d6dc006d41355f73a65.jpeg?from=327834062",
        "authorName": "卢昱晓",
        "authorSecUid": "MS4wLjABAAAAx69aAOrZxulx-D7hQ_s_IkM-GLmqU6NpV3dCG7vTzcI",
        "authorShortId": "1109107012",
        "authorUid": "71627837924",
        "authorUniqueId": "",
        "collectCount": 299938,
        "commentCount": 53141,
        "content": "好美的歌～别辜负眼前季节…🌱🌸#咏春 #手语 谢谢：@sea℃ #星动营业中 #剧组修炼手册",
        "coverUrl": "https://p5-ex-gddgtc-sign.douyinpic.com/tos-cn-i-0813c001/o4pCgTWfAAfTWg6g04AhfYeAAACQDAve4f2f27e~noop.webp?lk3s=138a59ce&x-expires=1782493200&x-signature=guKm9QqNm1p6032FDhg1U4W3z5U%3D&from=327834062_large&s=PackSourceEnum_CHALLENGE_AWEME&se=false&sc=cover&biz_tag=aweme_video&l=20260613014941BE1DE20BD0DA2DA1CEEE",
        "duration": 52383,
        "imageUrlList": [],
        "likeCount": 6321932,
        "opusUrl": "https://www.iesdouyin.com/share/video/7617768400190490538",
        "publishTime": "2026-03-16 16:32:01",
        "shareCount": 511238,
        "tagList": [
          {
            "tagId": "7537210021860689970",
            "tagName": "剧组修炼手册"
          },
          {
            "tagId": "1568982534901762",
            "tagName": "咏春"
          },
          {
            "tagId": "1569975134269506",
            "tagName": "手语"
          },
          {
            "tagId": "7532156586656008238",
            "tagName": "星动营业中"
          }
        ],
        "videoId": "7617768400190490538",
        "videoType": "0"
      }
    ],
    "pageNum": 1,
    "pageSize": 10,
    "total": 138614011
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
API_URL = 'https://redfox.hk/story/api/dy/data/searchWork'


class RedFoxHubError(RuntimeError):
    """Raised when RedFoxHub cannot complete a request."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='搜索关键词获取抖音作品 (广域库)')
    parser.add_argument('keyword')
    parser.add_argument('--exact-match', action='store_true')
    parser.add_argument('--start-date', default=None)
    parser.add_argument('--end-date', default=None)
    parser.add_argument('--page-num', type=int, default=1)
    parser.add_argument('--page-size', type=int, default=10)
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
        'startDate': args.start_date,
        'endDate': args.end_date,
        'pageNum': args.page_num,
        'pageSize': args.page_size,
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
