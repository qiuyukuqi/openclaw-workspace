# 🛠️ 服务器完整部署指南

> 腾讯云 Ubuntu 22.04 服务器，OpenClaw AI助手 + 自动化脚本 + 定时任务
> 作者：秋雨哭泣 | 最后更新：2026-04-07

---

## 📋 目录

- [环境概览](#环境概览)
- [核心服务](#核心服务)
- [技能(Skills)说明](#技能skills说明)
- [工具脚本说明](#工具脚本说明)
- [定时任务(Cron)](#定时任务cron)
- [Systemd服务](#systemd服务)
- [环境变量配置](#环境变量配置)
- [重装系统恢复步骤](#重装系统恢复步骤)

---

## 环境概览

| 项目 | 信息 |
|------|------|
| 系统 | Ubuntu 22.04 LTS (x64) |
| IP | 43.135.179.141 |
| AI框架 | OpenClaw |
| Python | 3.12 |
| Node.js | v22.22.1 |
| 浏览器自动化 | Playwright (Chromium) |
| AI模型 | DeepSeek (写作) + 智谱AI (生图/OCR) |
| 搜索API | Tavily |
| 渠道 | 飞书(Feishu) |
| GitHub仓库 | https://github.com/qiuyukuqi/openclaw-workspace.git |

### 已安装系统包

```bash
playwright, clawteam, requests, beautifulsoup4, openclaw
Chromium (via playwright install chromium)
ffmpeg
```

---

## 核心服务

### OpenClaw Gateway
OpenClaw是AI助手框架，通过飞书与企业微信(备用)与用户交互。

- **工作目录**: `~/.openclaw/workspace/`
- **配置文件**: `~/.openclaw/config.yaml`
- **技能目录**: `~/.openclaw/workspace/skills/`

### Windows辅助服务器
用于登录需要GUI的平台（头条号、小红书等），导出Cookie到Linux服务器。

- **IP**: 43.135.179.141 (RDP)
- **项目**: `C:\Users\Administrator\auto-publisher\`
- **Cookie导出脚本**: `export_all.py`
- **SSH密码**: 见TOOLS.md

---

## 技能(Skills)说明

### 1. 📰 微信公众号发布 (`wechat-publisher`)

**功能**: AI自动写文章 → 排版 → 生图 → 发布到公众号草稿箱

**脚本**: `skills/wechat-publisher/scripts/pipeline.py`

**流水线步骤** (7步):
1. **Scout选题** → Tavily搜索近3天热点 → DeepSeek筛选
2. **Research调研** → 围绕选题搜索资料
3. **Writer写文** → DeepSeek生成3000字公众号文章（风格：犀利观点鲜明）
4. **Polish润色** → AI润色标题/错别字/过渡
5. **Director配图** → AI规划配图提示词
6. **Image生图** → 通义万相API生成配图
7. **Format排版** → HTML排版 + 插图
8. **Publish发布** → 微信公众号API发到草稿箱

**运行**:
```bash
cd ~/.openclaw/workspace
python3 skills/wechat-publisher/scripts/pipeline.py --auto   # 全自动
python3 skills/wechat-publisher/scripts/pipeline.py            # 交互(每步审核)
python3 skills/wechat-publisher/scripts/pipeline.py --step write  # 从指定步骤开始
```

**日志**: `skills/wechat-publisher/data/auto_publish.log`

**配置**: `.env.wechat` (APP_ID, APP_SECRET)

---

### 2. 🚀 全平台内容分发 (`auto-publisher`)

**功能**: 一条命令完成：选题 → 写文 → 公众号发布 → 改编 → 头条号+小红书分发

**主脚本**: `skills/auto-publisher/full_pipeline.py`

**流水线步骤** (10步):
1-8. 同上(公众号流水线)
9. **Adapt改编** → AI改编为头条版(完整) + 小红书版(精简500字+emoji)
10. **Distribute分发** → Playwright自动发布到头条号 + 小红书

**运行**:
```bash
cd ~/.openclaw/workspace
python3 skills/auto-publisher/full_pipeline.py --auto       # 全自动
python3 skills/auto-publisher/full_pipeline.py               # 交互模式
python3 skills/auto-publisher/full_pipeline.py --step adapt  # 从改编步骤开始
```

**依赖Cookie**:
- 头条号: `/tmp/openclaw/toutiao_cookies.json` (从Windows服务器导出)
- 小红书: `/tmp/openclaw/xiaohongshu_cookies.json` (从Windows服务器导出)

**Cookie导出** (在Windows服务器上):
```bash
cd C:\Users\Administrator\auto-publisher
python export_all.py toutiao
python export_all.py xiaohongshu
```

**Cookie拉取** (到Linux服务器):
```bash
scp Administrator@43.135.179.141:"C:/Users/Administrator/auto-publisher/auth/toutiao_storage_state.json" /tmp/openclaw/toutiao_cookies.json
scp Administrator@43.135.179.141:"C:/Users/Administrator/auto-publisher/auth/xiaohongshu_storage_state.json" /tmp/openclaw/xiaohongshu_cookies.json
```

**子模块**:
- `platforms/toutiao.py` — 头条号发布器 (Playwright + cookie注入 + save=1直接提交审核)
- `platforms/xiaohongshu.py` — 小红书发布器 (Playwright + cookie注入 + 图文模式)
- `platforms/zhihu.py` — 知乎发布器 (⚠️ 受安全验证限制，暂不可用)
- `core/wechat_reader.py` — 公众号文章读取器
- `core/markdown_converter.py` — Markdown转换工具
- `distribute.py` — 独立分发入口

---

### 3. 📧 邮箱监控 (`email-monitor`)

**功能**: 监控酒钢企业邮箱(fuwanqiang@jiugang.com)，新邮件自动总结推送到飞书

**脚本**:
- `scripts/check_mail.py` — 邮件轮询检查（Systemd服务，持续运行）
- `scripts/daily_report.sh` — 每日邮件日报汇总
- `scripts/news_rss.py` — 每日新闻简报（天气+国际+IT新闻）

**配置**: `.env.email` (IMAP服务器、密码等)

---

### 4. ⏰ 倒班提醒 (`shift-reminder`)

**功能**: 4天一轮倒班制自动提醒

**班次**: 夜班 → 下夜班+休息 → 休息 → 白班
**起始**: 2026年2月13日（周五）夜班

**脚本**: `skills/shift-reminder/scripts/shift_reminder.js`

**提醒规则**:
| 班次 | 时间 | 内容 |
|------|------|------|
| 夜班 | 工作日19:20 / 周末19:50 | ⏰ 夜班上班了，抓紧刷脸！ |
| 下夜班 | 08:50 | 🌅 下班了，抓紧刷脸！ |
| 白班 | 07:50, 20:50 | ⏰ 上班了 / 🌙 下班了 |

---

### 5. 🎵 Suno音乐生成 (`suno-music`)

**功能**: 通过302.ai调用Suno V5生成歌曲

**脚本**: `scripts/suno_music.sh`

**运行**:
```bash
bash scripts/suno_music.sh "描述文字"           # 带人声歌曲
bash scripts/suno_music.sh "描述" chirp-crow true  # 纯音乐
```

**输出**: `/tmp/openclaw/music/`

**配置**: `.env.suno` 或环境变量

---

### 6. 🔍 Tavily搜索 (`tavily`)

**功能**: AI优化的网页搜索API

**脚本**: `skills/tavily/scripts/tavily_search.py`

**配置**: `.env.tavily` (API Key)

---

### 7. 🔤 腾讯OCR (`tencent-ocr`)

**功能**: 图片文字识别（通用/手写）

**脚本**: `skills/tencent-ocr/scripts/ocr.py`

**运行**:
```bash
python3 skills/tencent-ocr/scripts/ocr.py image.png [general|fast|handwriting]
```

**配置**: `.env.tencent` (SecretId, SecretKey)

---

### 8. 📚 知识库 (`knowledge-base`)

**功能**: 个人知识库RAG系统，上传文件(PDF/Word/TXT/MD) → 向量化 → 智能检索

**脚本**: `skills/knowledge-base/scripts/kb_manager.py`

---

### 9. 🌐 Agent Browser (`agent-browser`)

**功能**: 无头浏览器自动化CLI，支持页面导航/点击/输入/截图

---

### 10. 🤖 ClawTeam (`clawteam`)

**功能**: 多Agent协作框架，通过tmux+git worktree实现并行任务

**注意**: 当前场景用`full_pipeline.py`单脚本更合适，ClawTeam适合并行独立任务

---

## 工具脚本说明

| 脚本 | 功能 | 依赖 |
|------|------|------|
| `scripts/suno_music.sh` | Suno AI音乐生成 | 302.ai API |
| `scripts/text2img.sh` | 智谱AI文字生图 | 智谱API |
| `scripts/text2video.sh` | 智谱AI文字生视频 | 智谱API |
| `scripts/asr.sh` | 智谱AI语音转文本 | 智谱API |
| `scripts/voice_clone.sh` | 智谱AI音色复刻 | 智谱API |
| `scripts/rerank.sh` | 文本重排序 | 智谱API |
| `scripts/doc_parse.sh` | 文档解析(OCR) | 智谱API |
| `scripts/make_cover.sh` | 文章封面生成 | Playwright |
| `scripts/flux_img.sh` | Flux图片生成 | ComfyUI |
| `scripts/memory-backup.sh` | LanceDB记忆备份 | - |
| `scripts/memory-healthcheck.sh` | LanceDB记忆健康检查 | - |
| `scripts/epms_watchdog.sh` | EPMS监控 | - |
| `scripts/egongtong_watch.sh` | e工地监控 | - |

**配置**: `.env.zhipu` (智谱API Key)

---

## 定时任务(Cron)

```cron
# ========== OpenClaw 系统 ==========
*/5 * * * * flock -xn /tmp/stargate.lock -c '/usr/local/qcloud/stargate/admin/start.sh > /dev/null 2>&1 &'

# ========== 记忆系统 ==========
0 * * * * /root/.openclaw/workspace/scripts/memory-healthcheck.sh     # 每小时记忆健康检查
0 */6 * * * /root/.openclaw/workspace/scripts/memory-backup.sh       # 每6小时记忆备份

# ========== 微信公众号 ==========
30 8 * * * cd /root/.openclaw/workspace && python3 skills/wechat-publisher/scripts/pipeline.py --auto >> skills/wechat-publisher/data/auto_publish.log 2>&1  # 每天8:30自动写文发布

# ========== 邮箱监控 ==========
0 7 * * * cd /root/.openclaw/workspace && /bin/bash skills/email-monitor/scripts/daily_report.sh >> skills/email-monitor/data/report.log 2>&1   # 每天7:00邮件日报
10 7 * * * cd /root/.openclaw/workspace && python3 skills/email-monitor/scripts/news_rss.py >> skills/email-monitor/data/news_rss.log 2>&1            # 每天7:10新闻简报

# ========== 倒班提醒 ==========
* * * * * cd /root/.openclaw/workspace && node skills/shift-reminder/scripts/shift_reminder.js >> skills/shift-reminder/data/cron.log 2>&1  # 每分钟检查
```

### Cron恢复命令
```bash
crontab -l > /tmp/crontab_backup.txt    # 导出
crontab /tmp/crontab_backup.txt          # 导入
```

---

## Systemd服务

### email-polling.service — 邮件轮询监控

```ini
[Unit]
Description=Email Polling Monitor
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /root/.openclaw/workspace/skills/email-monitor/scripts/check_mail.py
WorkingDirectory=/root/.openclaw/workspace
Restart=always
RestartSec=30
StandardOutput=append:/root/.openclaw/workspace/skills/email-monitor/data/polling.log
StandardError=append:/root/.openclaw/workspace/skills/email-monitor/data/polling.log

[Install]
WantedBy=multi-user.target
```

**管理命令**:
```bash
systemctl status email-polling    # 查看状态
systemctl restart email-polling   # 重启
journalctl -u email-polling -f    # 查看实时日志
```

---

## 环境变量配置

所有配置文件位于 `~/.openclaw/workspace/` 目录下：

| 文件 | 内容 | 示例 |
|------|------|------|
| `.env.wechat` | 微信公众号 | APP_ID=wx..., APP_SECRET=... |
| `.env.email` | 邮箱监控 | IMAP服务器、密码 |
| `.env.tavily` | Tavily搜索 | TAVILY_API_KEY=tvly-... |
| `.env.tencent` | 腾讯OCR | SecretId=..., SecretKey=... |
| `.env.zhipu` | 智谱AI | ZHIPU_API_KEY=... |
| `.env.youtube` | YouTube | API Key |
| `.env.suno` | Suno音乐 | 302.ai API |

⚠️ **重要**: `.env`文件包含密钥，已在`.gitignore`中排除。重装时需手动配置。

---

## 重装系统恢复步骤

### 1. 系统初始化
```bash
# 更新系统
apt update && apt upgrade -y

# 安装基础依赖
apt install -y python3 python3-pip nodejs npm git ffmpeg curl wget \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libasound2 libpango-1.0-0 libcairo2 fonts-noto-cjk

# 安装Playwright
pip3 install playwright requests beautifulsoup4
playwright install chromium

# 安装OpenClaw
npm install -g openclaw

# 安装ClawTeam
pip3 install clawteam

# 安装SSH工具（用于从Windows导出Cookie）
apt install -y sshpass
```

### 2. 克隆配置仓库
```bash
cd ~
git clone https://github.com/qiuyukuqi/openclaw-workspace.git ~/.openclaw/workspace
cd ~/.openclaw/workspace

# 安装Node.js依赖（倒班提醒等）
npm install
```

### 3. 配置环境变量
```bash
# 手动创建.env文件，填入API密钥
cp .env.example .env.wechat
cp .env.example .env.email
cp .env.example .env.tavily
cp .env.example .env.tencent
cp .env.example .env.zhipu
# 然后编辑每个文件填入实际值
```

### 4. 初始化OpenClaw
```bash
openclaw init
openclaw gateway start
openclaw gateway status
```

### 5. 恢复定时任务
```bash
crontab ~/.openclaw/workspace/crontab.conf
```

### 6. 恢复Systemd服务
```bash
cp ~/.openclaw/workspace/systemd/email-polling.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable email-polling
systemctl start email-polling
```

### 7. 导入Cookie（从Windows服务器）
```bash
mkdir -p /tmp/openclaw
sshpass -p '密码' scp Administrator@43.135.179.141:"C:/Users/Administrator/auto-publisher/auth/toutiao_storage_state.json" /tmp/openclaw/toutiao_cookies.json
sshpass -p '密码' scp Administrator@43.135.179.141:"C:/Users/Administrator/auto-publisher/auth/xiaohongshu_storage_state.json" /tmp/openclaw/xiaohongshu_cookies.json
```

### 8. 恢复记忆数据库
```bash
# 如果有备份（在 ~/.openclaw/memory/backups/）
# LanceDB会自动创建，但如有旧数据可从备份恢复
```

### 9. 验证
```bash
# 检查所有服务
systemctl status email-polling
crontab -l

# 测试OpenClaw
openclaw gateway status

# 测试脚本
python3 skills/shift-reminder/scripts/shift_reminder.js status
python3 skills/email-monitor/scripts/check_mail.py --once
```

---

## 文件结构

```
~/.openclaw/workspace/
├── AGENTS.md              # AI助手行为规范
├── SOUL.md                # AI人格定义
├── USER.md                # 用户信息
├── TOOLS.md               # 工具使用笔记
├── MEMORY.md              # 长期记忆
├── HEARTBEAT.md           # 心跳任务
├── IDENTITY.md            # 身份信息
├── .env.wechat            # 微信公众号配置
├── .env.email             # 邮箱配置
├── .env.tavily            # Tavily配置
├── .env.tencent           # 腾讯OCR配置
├── .env.zhipu             # 智谱AI配置
├── .env.youtube           # YouTube配置
│
├── scripts/               # 通用工具脚本
│   ├── suno_music.sh      # Suno音乐生成
│   ├── text2img.sh        # 智谱生图
│   ├── text2video.sh      # 智谱生视频
│   ├── asr.sh             # 语音转文本
│   ├── voice_clone.sh     # 音色复刻
│   ├── rerank.sh          # 文本重排序
│   ├── doc_parse.sh       # 文档解析
│   ├── make_cover.sh      # 封面生成
│   ├── memory-backup.sh   # 记忆备份
│   ├── memory-healthcheck.sh  # 记忆健康检查
│   └── ...
│
├── skills/                # 技能模块
│   ├── wechat-publisher/  # 公众号发布
│   ├── auto-publisher/    # 全平台分发
│   ├── email-monitor/     # 邮箱监控
│   ├── shift-reminder/    # 倒班提醒
│   ├── suno-music/        # 音乐生成
│   ├── tavily/            # 搜索
│   ├── tencent-ocr/       # OCR
│   ├── knowledge-base/    # 知识库
│   ├── agent-browser/     # 浏览器自动化
│   ├── clawteam/          # 多Agent协作
│   └── ...
│
├── memory/                # 每日记忆日志
│   ├── 2026-03-21.md
│   └── ...
│
└── crontab.conf           # Cron备份
```
