# /stuck — 进程诊断技能

检测本机进程异常（卡死、高CPU、内存泄漏、子进程挂起），输出诊断报告。

## 使用场景
- 服务器卡顿，需要排查哪个进程有问题
- 某个服务没有响应
- 怀疑有僵尸进程或内存泄漏

## 诊断步骤

1. **列出高资源进程**（CPU≥50% 或 RSS≥1GB）：
   ```bash
   ps aux --sort=-%cpu | head -20
   ps aux --sort=-rss | head -20
   ```

2. **检测僵尸进程（Z）和不可中断睡眠（D）**：
   ```bash
   ps aux | awk '$8 ~ /[ZD]/'
   ```

3. **检测OpenClaw相关进程状态**：
   ```bash
   ps aux | grep -E '(openclaw|node|playwright)' | grep -v grep
   ```

4. **检测高CPU持续情况**（采样两次确认）：
   ```bash
   # 第一次采样
   ps -p <PID> -o pid,%cpu,rss,etime,stat,comm
   sleep 2
   # 第二次采样
   ps -p <PID> -o pid,%cpu,rss,etime,stat,comm
   ```

5. **检查子进程挂起**：
   ```bash
   pgrep -lP <PID>
   ```

6. **检查磁盘IO**（可能D状态的进程在等IO）：
   ```bash
   iostat -x 1 3 2>/dev/null || cat /proc/diskstats | head -10
   ```

7. **检查系统负载**：
   ```bash
   uptime
   free -h
   df -h /
   ```

## 状态判断

| 状态 | 含义 | 建议 |
|------|------|------|
| `S` | 可中断睡眠（正常等待） | 正常 |
| `R` | 运行中 | 正常 |
| `D` | 不可中断睡眠（IO挂起） | 检查磁盘，可能需要reboot |
| `Z` | 僵尸进程 | 杀父进程或reboot |
| `T` | 被停止（Ctrl+Z） | `kill -CONT <PID>` 恢复 |
| CPU≥90%持续 | 可能无限循环 | 检查日志，可能需kill |
| RSS≥4GB | 可能内存泄漏 | 重启该服务 |

## 报告格式

```
🔍 系统诊断报告
─────────────────
负载: load average: x.xx
内存: used/total (xx%)
磁盘: / used/total (xx%)

⚠️ 异常进程:
- PID 12345, CPU 95%, RSS 2.1GB, 状态 R, 命令: node xxx
  诊断: 可能无限循环
  建议: kill 12345 并重启服务

✅ 无异常进程
```

## 注意事项
- 不要杀掉openclaw gateway本身（除非明确有问题）
- D状态的进程kill无效，只能reboot
- 僵尸进程杀不掉，需杀父进程或reboot
