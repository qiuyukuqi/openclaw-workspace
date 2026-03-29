---
name: email-monitor
description: 邮箱监控服务，定期检查邮箱中的新邮件，自动总结内容并推送到飞书，支持附件下载和转发。当用户要求监控邮箱、邮件通知、新邮件提醒、自动处理邮件时使用此技能。
---

# 邮箱监控服务

监控企业邮箱，检测新邮件，自动总结内容并推送到飞书聊天窗口。

## 功能

- 定期轮询检查未读邮件
- 自动总结邮件内容
- 下载附件并转发到飞书
- 支持多附件处理

## 配置

凭证存储于 `~/.openclaw/workspace/.env.email`：

```
EMAIL_IMAP_SERVER=mail.jiugang.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_SERVER=smtp.jiugang.com
EMAIL_SMTP_PORT=465
EMAIL_USER=your@email.com
EMAIL_PASSWORD=your_password
```

## 使用方式

### 手动检查

```bash
python skills/email-monitor/scripts/check_mail.py
```

### 定时任务（推荐）

通过 OpenClaw cron 设置定期检查：

```bash
# 每5分钟检查一次
openclaw cron add --schedule "*/5 * * * *" --command "python /root/.openclaw/workspace/skills/email-monitor/scripts/check_mail.py"
```

或手动添加到 crontab：

```bash
crontab -e
# 添加：
*/5 * * * * cd /root/.openclaw/workspace && python skills/email-monitor/scripts/check_mail.py >> skills/email-monitor/data/check.log 2>&1
```

## 推送格式

收到新邮件后，飞书会收到：

```
📧 新邮件通知

发件人：xxx@example.com
主题：会议通知
时间：Fri, 13 Mar 2026 10:30:00 +0800

内容预览：关于下周一的部门会议...

📎 附件 (2个)：
  • 会议议程.pdf (125.3KB)
  • 参会名单.xlsx (45.2KB)
```

附件会单独发送到聊天窗口。

## 数据存储

- `data/last_check.json` - 上次检查状态
- `data/attachments/` - 下载的附件
- `data/check.log` - 检查日志

## 注意事项

- 轮询间隔建议 5-10 分钟
- 附件大小限制取决于飞书 API
- 密码请使用授权码而非登录密码（如邮箱支持）
