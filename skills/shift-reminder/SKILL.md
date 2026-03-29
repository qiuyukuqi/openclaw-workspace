---
name: shift-reminder
description: "倒班日历提醒服务。4天一轮（夜班→下夜班+休息→休息→白班），自动推送上班/下班提醒到飞书。"
metadata:
  openclaw:
    emoji: "📅"
    requires:
      bins: ["node"]
---

# 倒班日历提醒

4天一轮的倒班提醒服务，自动推送到飞书。

## 班次周期与提醒

| 班次 | 提醒时间 | 提醒内容 |
|------|----------|----------|
| 夜班 | 工作日19:20 / 周末19:50 | ⏰ 夜班上班了，抓紧刷脸！ |
| 下夜班+休息 | 08:50 | 🌅 下班了，抓紧刷脸！ |
| 休息 | 无 | - |
| 白班 | 07:50, 20:50 | ⏰ 白班上班了 / 🌙 下班了 |

起始日期：2026年2月13日（周五）夜班

## 使用方法

```bash
# 查看倒班日历（今天+7天）
node skills/shift-reminder/scripts/shift_reminder.js test

# 查看今日班次详情
node skills/shift-reminder/scripts/shift_reminder.js status

# 运行提醒检查（用于 cron）
node skills/shift-reminder/scripts/shift_reminder.js
```

## 定时任务

建议每分钟检查一次：

```bash
* * * * * /usr/bin/node /root/.openclaw/workspace/skills/shift-reminder/scripts/shift_reminder.js >> /root/.openclaw/workspace/skills/shift-reminder/data/cron.log 2>&1
```

## 文件结构

```
skills/shift-reminder/
├── SKILL.md
├── scripts/
│   └── shift_reminder.js
└── data/
    ├── sent_reminders.json  # 已发送记录
    └── cron.log             # cron 日志
```

## 配置

- 飞书用户: `ou_c5c98e2002a34a9b10f15fd0b6463d06`
- 配置文件: `/root/.openclaw/gateway.json` (飞书凭证)
