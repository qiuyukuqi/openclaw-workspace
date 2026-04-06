# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## 302.ai — Suno AI 音乐生成

API Key: 见 `.env.suno` 或环境变量
脚本: `scripts/suno_music.sh`
技能: `skills/suno-music/SKILL.md`
音频输出: `/tmp/openclaw/music/`

| 功能 | 命令 |
|------|------|
| 生成歌曲 | `./scripts/suno_music.sh "描述"` |
| 纯音乐 | `./scripts/suno_music.sh "描述" chirp-crow true` |
| 自定义歌词 | API直接调用 `/suno/submit/music/custom` |

模型: `chirp-crow`(V5,推荐), `chirp-bluejay`(V4.5+), `chirp-v3-5`
价格: 0.1 PTC/次(~0.7元)，每次生成2首
耗时: 2-3分钟

---

## 通义万相 API（阿里 DashScope）

API Key: 见 `.env.dashscope` 或环境变量
端点: `https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis`
模型: `wanx-v1`
支持尺寸: `1024*1024`, `720*1280`, `1280*720`, `768*1152`（不支持1920*1080）
需要 `X-DashScope-Async: enable` 头，异步任务查询: `/api/v1/tasks/{task_id}`
注意: 动画风格+负面词（哭泣/sad/tears）会触发审核卡PENDING

---

## 智谱AI API

API Key: 见 `.env.zhipu` 或环境变量
脚本目录: `scripts/`

| 脚本 | 功能 | 命令 |
|------|------|------|
| text2img.sh | 文字生图 | `bash scripts/text2img.sh "描述"` |
| text2video.sh | 文字生视频 | `bash scripts/text2video.sh "描述"` |
| asr.sh | 语音转文本 | `bash scripts/asr.sh audio.wav` |
| voice_clone.sh | 音色复刻 | `bash scripts/voice_clone.sh sample.wav "文本"` |
| rerank.sh | 文本重排序 | `bash scripts/rerank.sh "查询" "候选1" "候选2"` |
| doc_parse.sh | 文档解析(OCR) | `bash scripts/doc_parse.sh doc.pdf` |

---

## 腾讯云 OCR

凭证存储位置: `~/.openclaw/workspace/.env.tencent`

使用方式:
```bash
python skills/tencent-ocr/scripts/ocr.py <图片路径或URL> [general|fast|handwriting]
```

---

## 邮箱监控

凭证存储位置: `~/.openclaw/workspace/.env.email`

当前邮箱：fuwanqiang@jiugang.com（酒钢企业邮箱）

**定时任务配置文件：** `skills/email-monitor/crontab.conf`

**恢复定时任务：** `cat ~/.openclaw/workspace/skills/email-monitor/crontab.conf | crontab -`

**当前定时任务：**
| 任务 | 时间 | 脚本 |
|------|------|------|
| 邮件日报 | 每天 7:00 | daily_report.sh |
| 新闻简报 | 每天 7:10 | news_rss.py |
| 倒班提醒 | 每分钟 | shift_reminder.js |

**Systemd 服务：**
| 服务 | 状态 | 说明 |
|------|------|------|
| email-polling.service | enabled | 邮件监控（持续运行，失败自动重启） |

**手动检查邮件：**
```bash
cd ~/.openclaw/workspace && python3 skills/email-monitor/scripts/check_mail.py --once
```

日志：`skills/email-monitor/data/check.log`

---

## 新闻RSS订阅（已固化）

**脚本路径：** `skills/email-monitor/scripts/news_rss.py`（标准，勿改为sh版）
**crontab标准：** `10 7 * * * cd /root/.openclaw/workspace && python3 skills/email-monitor/scripts/news_rss.py >> skills/email-monitor/data/news_rss.log 2>&1`

**数据源配置（禁止修改）：**
- 天气数据源：中国天气网 d1.weather.com.cn（单数据源）
- 嘉峪关城市ID：`101161401`
- 国际新闻源：https://news.sina.com.cn/world/
- IT新闻源：https://www.ithome.com/rss/
- 新闻过滤：排除体育、娱乐、游戏等关键词

**新闻简报格式（禁止修改）：**
```
📰 每日新闻简报
📅 2026年03月13日 星期五 07:10
──────────────────────────────
📍 嘉峪关 实时天气（07:00）

🌡️ 温度: -3.6℃
🌬️ 风向: 东南风
💨 风力: 2级
💧 湿度: 88%

📅 5天预报
今天 3/13 ☁️ 小雪转阴 -7 至 -1℃
明天 3/14 ☀️ 多云转晴 -6 至 5℃
后天 3/15 ☀️ 晴 -5 至 7℃
星期一 3/16 ☀️ 晴转多云 -4 至 9℃
星期二 3/17 ⛅ 多云转阴 -4 至 5℃
──────────────────────────────

【国际新闻】
1. 古特雷斯：已抵达黎巴嫩
2. 日方后知后觉：中国管制，关联日企有近万家！
3. 特朗普鼓动油轮"拿出点胆量"通过霍尔木兹海峡
4. 人民日报：事故频发，日本基建"人设"为何"塌房"？
5. 美军从中东撤离19名伤员

【IT简报】
1. 抖音回应苹果调整中国区 App Store 佣金...
2. 国家网络安全通报中心发布 OpenClaw 安全风险预警
3. 金融监管总局约谈分期乐...
4. 小车也有激光雷达，零跑全新纯电车型 A05 申报
5. 蓝宝石 PURE 极地 X870A WIFI7 主板上架

──────────────────────────────
```

**新闻过滤规则（禁止修改）：**
```python
NEWS_FILTER = [
    "切尔西", "皇马", "巴萨", "曼联", "曼城", "利物浦", "阿森纳",
    "NBA", "CBA", "中超", "英超", "西甲", "意甲", "德甲", "法甲",
    "娱乐", "明星", "综艺", "电视剧", "电影", "歌手",
    "游戏", "电竞", "直播"
]
```

**定时任务：** Cron 每天 7:10

**手动测试：**
```bash
cd ~/.openclaw/workspace && python3 skills/email-monitor/scripts/news_rss.py
```

**状态文件：** `skills/email-monitor/data/news_state.json`

---

## 倒班日历提醒（已固化）

**脚本路径：** `skills/shift-reminder/scripts/shift_reminder.js`（标准，勿改为sh版）
**crontab标准：** `* * * * * cd /root/.openclaw/workspace && node skills/shift-reminder/scripts/shift_reminder.js >> skills/shift-reminder/data/cron.log 2>&1`

**班次周期（禁止修改）：**
- 4天一轮：夜班 → 下夜班+休息 → 休息 → 白班
- 起始日期：2026年2月13日（周五）夜班

**提醒规则（禁止修改）：**
| 班次 | 提醒时间 | 提醒内容 |
|------|----------|----------|
| 夜班 | 工作日19:20 / 周末19:50 | ⏰ 夜班上班了，抓紧刷脸！ |
| 下夜班+休息 | 08:50 | 🌅 下班了，抓紧刷脸！ |
| 休息 | 无 | - |
| 白班 | 07:50, 20:50 | ⏰ 白班上班了 / 🌙 下班了 |

**定时任务：** Cron 每分钟检查

**手动测试：**
```bash
cd ~/.openclaw/workspace && node skills/shift-reminder/scripts/shift_reminder.js test    # 查看日历
cd ~/.openclaw/workspace && node skills/shift-reminder/scripts/shift_reminder.js status  # 今日班次
```

**日志文件：** `skills/shift-reminder/data/cron.log`

---

Add whatever helps you do your job. This is your cheat sheet.
