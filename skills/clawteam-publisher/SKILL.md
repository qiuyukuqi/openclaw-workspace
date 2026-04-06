# ClawTeam 多Agent公众号涨粉系统

## 概述
使用ClawTeam多agent协作，自动完成：选题→写作→配图→发布公众号→跨平台分发（知乎/小红书/头条号）。

## Agent分工
- **leader**: 协调整体流程（Jarvis主agent担任）
- **scout**: 热点监控+选题挖掘
- **writer**: 公众号文章写作+润色
- **distributor**: 跨平台内容改编（知乎/小红书/头条号）

## 每日工作流

### Step 1: Leader发起（每天早上）
```bash
# 创建团队
clawteam team spawn-team wechat-growth -d "每日公众号内容生产+跨平台分发" -n leader

# 启动scout agent
clawteam spawn tmux openclaw --team wechat-growth \
  --agent-name scout \
  --task "搜索今日AI/科技领域热点新闻，输出5个候选选题，每个包含：标题、角度、热度评分(1-10)、实操价值(1-10)。用中文输出。"
```

### Step 2: Leader审核选题后启动writer
```bash
clawteam spawn tmux openclaw --team wechat-growth \
  --agent-name writer \
  --task "根据以下选题写一篇2000字左右的微信公众号文章：[选题内容]。要求：吸引人的开头、3-4个小标题、有观点有态度、结尾引导关注。用中文输出markdown格式。"
```

### Step 3: Leader启动distributor
```bash
clawteam spawn tmux openclaw --team wechat-growth \
  --agent-name distributor \
  --task "将以下文章改编为3个平台的版本：[文章内容]
  1. 知乎回答版（1000字，适合问答格式，文末引导关注公众号）
  2. 小红书图文版（300字+5个要点列表，标题带数字+情绪词）
  3. 头条号文章版（直接可用，SEO友好）
  用中文输出。"
```

### Step 4: Leader执行发布
```bash
# 将文章保存后执行公众号发布pipeline
cd ~/.openclaw/workspace && python3 skills/wechat-publisher/scripts/pipeline.py --auto --step publish
```

## 跨平台分发内容存储
- 知乎版: `/tmp/openclaw/wechat-publisher/cross-platform/zhihu_{date}.md`
- 小红书版: `/tmp/openclaw/wechat-publisher/cross-platform/xiaohongshu_{date}.md`
- 头条号版: `/tmp/openclaw/wechat-publisher/cross-platform/toutiao_{date}.md`

## 一键执行脚本
```bash
# 完整每日流程（需tmux环境）
~/.openclaw/workspace/scripts/clawteam_daily_publish.sh
```

## 注意事项
- scout/writer/distributor是独立的OpenClaw agent，各占一个tmux窗口
- 所有agent共享同一个Gateway，但会话隔离
- 跨平台内容生成后需手动发布到对应平台（知乎/小红书/头条号无公开API）
- 公众号发布可全自动（已有pipeline.py）
