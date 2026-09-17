---
name: bilibili-reach
description: Download Bilibili videos for free first, with paid RedFoxHub fallback; search videos and accounts through RedFoxHub.
user-invocable: true
load-experiences: false
metadata:
  bamboo:
    tags:
      - bilibili
      - video
      - retrieval
      - redfoxhub
---

# Bilibili Reach

## When to Use

Use this skill for video download, keyword video search, keyword account search, video detail, and account video list.

Do not use this skill for undocumented Bilibili APIs, browser automation, login-only data, comments, danmaku, favorites, or state-changing actions.

## Authentication

`download_video_free.py` needs no API key. The other scripts require `REDFOX_API_KEY`, usually loaded from `~/.bamboo/.env`.

## 视频下载顺序（必须遵循）

1. 先运行 `download_video_free.py URL --output-dir OUTPUT_DIR`，使用 yt-dlp 直接下载，不调用收费接口。依赖安装：`python -m pip install -U yt-dlp`；建议安装 ffmpeg，以便合并高清音视频。默认保存到当前目录下的 `downloads`，默认总超时 600 秒，可用 `--timeout` 调整。
2. 返回码为 0 时，向用户交付 stdout 中的本地文件路径，结束下载任务，不再调用 RedFox。
3. 仅当免费脚本返回非零状态（包括缺少依赖、限流、下载错误或超时）时，告知用户免费方式失败，随后运行现有 `download_video.py URL`，使用收费的 RedFox 接口兜底。用户明确取消时不要兜底。两个脚本不要并行执行。
4. RedFox 脚本只返回 JSON 中的 `data.videoUrl` 或 `data.resources[].downloadUrl`，并不保存视频。检查业务状态及非空视频链接后，若任务要求本地文件，继续将视频资源下载至用户指定目录，下载成功后再报告完成；接口报错或没有视频链接时报告失败。

免费脚本要求 `yt-dlp>=2026.8.19`；旧版提取器可能对公开视频返回 HTTP 412。若提示版本过旧，先执行 `python -m pip install -U 'yt-dlp>=2026.8.19'` 再重试免费脚本，仍失败才使用 RedFox。

免费脚本只下载指定视频，不批量下载合集。可通过 `--cookies /path/to/cookies.txt` 显式提供用户自己的 Netscape 格式 cookies；默认匿名下载，不读取浏览器登录信息。可用画质取决于当前账号权限及站点限制。

## Scripts

```bash
python <skill_dir>/scripts/download_video_free.py "https://www.bilibili.com/video/BV1AmSSBMEqo/" --output-dir ./downloads
# Only after the free download fails:
python <skill_dir>/scripts/download_video.py "https://www.bilibili.com/video/BV1AmSSBMEqo/"
python <skill_dir>/scripts/search_videos.py "羽绒服" --page 1 --page-size 10 --order time
python <skill_dir>/scripts/search_accounts.py "影视飓风" --page 1 --page-size 10 --order follower
python <skill_dir>/scripts/get_video.py --bv-id BV1ghJg6hEWV
python <skill_dir>/scripts/get_video.py --work-url "https://www.bilibili.com/video/BV1ghJg6hEWV/"
python <skill_dir>/scripts/list_account_videos.py --mid 946974 --page 1 --page-size 10 --order time
python <skill_dir>/scripts/list_account_videos.py --account-url "https://space.bilibili.com/946974"
```

RedFox scripts include the official request and response examples at the top of each file. The free download script documents its own usage and output at the top.
