---
name: suno-music
description: AI音乐生成。通过302.ai调用Suno V5，根据文字描述自动生成歌曲（含歌词、音频、视频）。当用户要求生成歌曲、创作音乐、写首歌、AI音乐时使用此技能。触发词：生成歌曲、创作音乐、写首歌、AI音乐、Suno、make a song。

---

# Suno AI 音乐生成

## 概述

通过302.ai API调用Suno V5模型，输入一段文字描述即可自动生成完整歌曲（歌词+人声+伴奏+封面+视频）。

## 可用模型

| 模型 | 代码 | 说明 |
|------|------|------|
| Suno V5 | `chirp-crow` | 最新最强，推荐默认 |
| Suno V4.5+ | `chirp-bluejay` | V4.5增强版 |
| Suno V4.5 | `chirp-auk` | V4.5标准版 |
| Suno V4 | `chirp-v4` | V4 |
| Suno V3.5 | `chirp-v3-5` | V3.5 |

## 使用方式

### 脚本调用
```bash
./scripts/suno_music.sh "歌曲描述" [模型] [纯音乐]
```

- 歌曲描述：英文效果更好，支持中文关键词
- 模型：默认 `chirp-crow`（V5）
- 纯音乐：`true`/`false`，默认 `false`

### API直接调用（推荐，更灵活）

**提交任务：**
```bash
curl -s "https://api.302.ai/suno/submit/music" \
  -H "Authorization: Bearer sk-VRTrDBlfKY1TXdffDiDNJtgUajH0EY7AN15pLWN1GDVbZC6c" \
  -H "Content-Type: application/json" \
  -d '{
    "mv": "chirp-crow",
    "gpt_description_prompt": "描述内容",
    "make_instrumental": false
  }'
# 返回: {"code":200,"data":"<task_id>","message":"success"}
```

**查询结果：**
```bash
curl -s "https://api.302.ai/suno/fetch/{task_id}" \
  -H "Authorization: Bearer sk-VRTrDBlfKY1TXdffDiDNJtgUajH0EY7AN15pLWN1GDVbZC6c"
# 返回包含 audio_url, video_url, title, prompt(歌词), tags, duration 等
```

**自定义模式（用户提供歌词+风格）：**
```bash
POST https://api.302.ai/suno/submit/music/custom
{
  "mv": "chirp-crow",
  "title": "歌名",
  "tags": "pop, ballad, female vocal, piano",
  "prompt": "歌词内容...",
  "make_instrumental": false
}
```

## 工作流程

1. 用户描述想要的歌曲（风格、主题、语言、歌手类型等）
2. 用英文构建 prompt（描述越详细越好）
3. 提交异步任务，等待2-3分钟
4. 获取结果，下载音频发送给用户
5. 一次调用自动生成2个版本

## Prompt技巧

- **语言**：描述用英文，歌词自动生成中文
- **风格**：指定 genre, mood, instruments, vocal type
- **时长**：约3-4分钟，无法精确控制
- **示例**：`"A emotional Chinese pop ballad about autumn rain and tears, female vocal, soft piano and strings, melancholic and beautiful"`

## 输出文件

- 音频：`/tmp/openclaw/music/{标题}_v1.mp3` / `_v2.mp3`
- 歌词：`/tmp/openclaw/music/{标题}_lyrics.txt`
- 视频URL：响应中 `video_url` 字段

## 价格

- 0.1 PTC/次（约0.7元人民币），每次生成2首
- 查询免费

## 注意事项

- 生成耗时约2-3分钟
- 每次调用生成2个不同编曲版本
- 支持中文歌词自动生成
- 可生成纯音乐（`make_instrumental: true`）
- 音频URL有时效性，生成后请及时下载
