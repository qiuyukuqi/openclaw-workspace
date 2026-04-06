# /stuck — 进程诊断技能（v2，源自Claude Code stuck.ts + bashSecurity）

检测本机进程异常（卡死、高CPU、内存泄漏、子进程挂起），输出诊断报告。

## 使用场景
- 服务器卡顿，需要排查哪个进程有问题
- 某个服务没有响应
- 怀疑有僵尸进程或内存泄漏

## 诊断步骤（按优先级）

### 1. 系统概览
```bash
uptime
free -h
df -h /
iostat -x 1 3 2>/dev/null || cat /proc/diskstats | head -10
```

### 2. 高资源进程（CPU≥50% 或 RSS≥1GB）
```bash
ps aux --sort=-%cpu | head -20
ps aux --sort=-rss | head -20
```

### 3. 异常进程状态
```bash
ps aux | awk '$8 ~ /[ZD]/'
```

### 4. 采样确认（排除瞬态峰值）
```bash
ps -p <PID> -o pid,%cpu,rss,etime,stat,comm
sleep 2
ps -p <PID> -o pid,%cpu,rss,etime,stat,comm
```

### 5. 子进程检查
```bash
pgrep -lP <PID>
```

### 6. OpenClaw相关
```bash
ps aux | grep -E '(openclaw|node|playwright)' | grep -v grep
```

## 状态判断表

| 状态 | 含义 | 建议 |
|------|------|------|
| `S` | 可中断睡眠（正常等待） | 正常 |
| `R` | 运行中 | 正常 |
| `D` | 不可中断睡眠（IO挂起） | 检查磁盘，可能需要reboot |
| `Z` | 僵尸进程 | 杀父进程或reboot |
| `T` | 被停止（Ctrl+Z） | `kill -CONT <PID>` 恢复 |
| CPU≥90%持续≥5s | 可能无限循环 | 检查日志，可能需kill |
| RSS≥4GB | 可能内存泄漏 | 重启该服务 |

## 诊断经验（源自Claude Code stuck.ts）

- **高CPU持续**：采样两次确认非瞬态。≥90%持续→无限循环
- **状态D**：I/O挂起，kill无效，只能reboot
- **RSS≥4GB**：内存泄漏，需要重启服务而非杀进程
- **子进程hang**：`pgrep -lP <pid>` 检查，可能需要清理孤儿进程

## 安全注意事项（源自Claude Code bashSecurity）
- 诊断命令只读，不修改系统状态
- 不要杀掉openclaw gateway本身（除非明确有问题）
- 不要用-i标志（交互式不支持）
- zombie进程kill不掉，需杀父进程或reboot
