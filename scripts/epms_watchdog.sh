#!/bin/bash
# EPMS监控看门狗 - 每5分钟检查一次
# 1. 进程是否存活  2. 数据是否在更新  3. 日志是否过大
set -euo pipefail

LOG_FILE="/root/.openclaw/workspace/scripts/epms_monitor.log"
SERVICE="epms-monitor"
MAX_LOG_SIZE=10485760  # 10MB
MAX_DATA_GAP=300       # 数据停滞5分钟

# 1. 进程检查
if ! systemctl is-active --quiet "$SERVICE"; then
    echo "[$(date)] 进程未运行，启动服务" >> "$LOG_FILE"
    systemctl start "$SERVICE"
    exit 0
fi

# 2. 数据更新检查（日志最后一条时间与当前时间差）
if [ -f "$LOG_FILE" ]; then
    last_ts=$(date -d "$(tail -1 "$LOG_FILE" | grep -oP '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')" +%s 2>/dev/null || echo 0)
    now_ts=$(date +%s)
    gap=$((now_ts - last_ts))
    if [ "$gap" -gt "$MAX_DATA_GAP" ]; then
        echo "[$(date)] 数据停滞${gap}秒，重启服务" >> "$LOG_FILE"
        systemctl restart "$SERVICE"
    fi
fi

# 3. 日志轮转
if [ -f "$LOG_FILE" ] && [ "$(stat -c%s "$LOG_FILE")" -gt "$MAX_LOG_SIZE" ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
    touch "$LOG_FILE"
    echo "[$(date)] 日志已轮转" >> "$LOG_FILE"
fi
